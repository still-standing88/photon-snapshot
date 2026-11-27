"""Qt-independent batch preparation and conversion with typed results."""
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter
import os
import threading
import json
from .formats import is_image_file, get_format
from .effects_catalog import validate_effect
from .processing import apply_effect
from .animation_io import decode_document
from .export import ExportOptions, export_document, CancelledError, check_cancel


@dataclass(frozen=True)
class SourceEntry:
    path: str
    recursive: bool = False
    formats: tuple = ()


@dataclass(frozen=True)
class DestinationOptions:
    target_folder: str = ''
    preserve_subfolders: bool = False
    overwrite_existing: bool = False
    delete_originals: bool = False
    log_file_path: str = ''


@dataclass(frozen=True)
class BatchSettings:
    export: ExportOptions = field(default_factory=ExportOptions)
    effects: tuple = ()
    destination: DestinationOptions = field(default_factory=DestinationOptions)
    animation_handling: str = 'preserve'


@dataclass(frozen=True)
class WorkItem:
    source: Path
    output: Path
    root: Path
    conflict: str = ''


@dataclass(frozen=True)
class FileResult:
    source: str
    status: str
    outputs: tuple = ()
    message: str = ''


@dataclass
class BatchResult:
    files: list = field(default_factory=list)
    discovery_errors: list = field(default_factory=list)

    @property
    def counts(self):
        counts = Counter(r.status for r in self.files)
        return {k: counts[k] for k in ('converted', 'skipped', 'failed', 'cancelled')}

    @property
    def summary(self):
        return ', '.join(f'{n} {k}' for k, n in self.counts.items())


class JobControl:
    def __init__(self):
        self.cancelled = threading.Event()
        self.running = threading.Event()
        self.running.set()

    def cancel(self):
        self.cancelled.set()
        self.running.set()

    def pause(self):
        self.running.clear()

    def resume(self):
        self.running.set()

    def checkpoint(self):
        while not self.running.wait(.1):
            check_cancel(self.cancelled.is_set)
        check_cancel(self.cancelled.is_set)


def identity(path):
    return os.path.normcase(os.path.realpath(path))


def resolve_sources(entries, settings, control=None):
    control = control or JobControl()
    fmt = settings.export.validate()
    if settings.animation_handling not in ('preserve', 'first', 'separate'):
        raise ValueError('Invalid animation handling policy')
    for effect_id, values in settings.effects:
        validate_effect(effect_id, values)
    target = Path(settings.destination.target_folder).resolve() if settings.destination.target_folder else None
    if target and not target.is_dir():
        raise ValueError('Select an existing destination folder')
    seen, resolved, errors = set(), [], []
    for entry in entries:
        control.checkpoint()
        path = Path(entry.path).resolve()
        root = path if path.is_dir() else path.parent
        candidates = []
        if path.is_dir():
            def failed(exc):
                errors.append(str(exc))
            for folder, dirs, files in os.walk(path, followlinks=False, onerror=failed):
                control.checkpoint()
                dirs[:] = sorted(d for d in dirs if not Path(folder, d).is_symlink() and
                    not (hasattr(Path(folder, d), 'is_junction') and Path(folder, d).is_junction()) and
                    not (target and identity(Path(folder, d)) == identity(target)))
                for name in sorted(files, key=str.casefold):
                    candidates.append(Path(folder, name))
                if not entry.recursive:
                    break
        elif path.is_file():
            candidates = [path]
        else:
            errors.append(f'Source does not exist: {path}')
        for source in candidates:
            control.checkpoint()
            if not is_image_file(source) or (entry.formats and get_format(source.suffix).id not in entry.formats):
                continue
            if target and source.is_relative_to(target) and target != root:
                continue
            canonical = identity(source)
            if canonical in seen:
                continue
            seen.add(canonical)
            folder = target or source.parent
            if target and settings.destination.preserve_subfolders:
                folder = target / root.name / source.parent.relative_to(root)
            output = folder / (source.stem + fmt.extension)
            resolved.append(WorkItem(source, output, root))
    outputs = Counter(identity(i.output) for i in resolved)
    log_id = identity(settings.destination.log_file_path) if settings.destination.log_file_path else None
    if log_id and (log_id in seen or log_id in outputs):
        raise ValueError('Log path conflicts with a source or output image')
    work = []
    for item in resolved:
        conflict = 'Destination is a queued source image' if identity(item.output) in seen else ''
        if outputs[identity(item.output)] > 1:
            conflict = 'Multiple source images resolve to the same destination'
        work.append(WorkItem(item.source, item.output, item.root, conflict))
    return tuple(work), errors


def run_batch(entries, settings, control=None, event=None):
    control = control or JobControl()
    emit = event or (lambda *args: None)
    result = BatchResult()
    emit('preparing', 0, 0, 'Preparing...')
    try:
        plan, errors = resolve_sources(entries, settings, control)
        result.discovery_errors.extend(errors)
    except CancelledError:
        return result
    for message in result.discovery_errors:
        emit('log', message)
    total = len(plan)
    if not total:
        emit('log', 'No supported image files found')
    for index, item in enumerate(plan):
        outputs = []
        try:
            control.checkpoint()
            emit('progress', index, total, str(item.source))
            if item.conflict:
                record = FileResult(str(item.source), 'skipped', message=item.conflict)
            elif item.output.exists() and not settings.destination.overwrite_existing and settings.animation_handling != 'separate':
                record = FileResult(str(item.source), 'skipped', message='Destination already exists')
            else:
                emit('phase', 'Decoding ' + item.source.name)
                try:
                    document = decode_document(item.source, control.cancelled.is_set, sequence_policy=settings.animation_handling)
                except ValueError as exc:
                    record = FileResult(str(item.source), 'skipped', message=str(exc))
                    result.files.append(record)
                    emit('result', record)
                    continue
                if document.animation and settings.animation_handling == 'preserve' and not get_format(settings.export.format_id).animation:
                    record = FileResult(str(item.source), 'skipped', message='Animated input requires GIF/WebP or an explicit frame choice')
                else:
                    for frame_index, frame in enumerate(document.frames):
                        control.checkpoint()
                        emit('phase', f'Preparing frame {frame_index+1} of {len(document.frames)}')
                        for effect_id, values in settings.effects:
                            control.checkpoint()
                            frame.image.current = apply_effect(frame.image.current, effect_id, values)
                    document.validate()
                    item.output.parent.mkdir(parents=True, exist_ok=True)
                    ids = {document.frames[0].id} if settings.animation_handling == 'first' else None
                    if settings.animation_handling == 'separate' and len(document.frames) > 1:
                        folder = item.output.parent / (item.source.stem + '_frames')
                        folder.mkdir(parents=True, exist_ok=True)
                        paths = [folder / f'{item.source.stem}_{i+1:06d}{get_format(settings.export.format_id).extension}' for i in range(len(document.frames))]
                        if any(identity(p) in {identity(w.source) for w in plan} for p in paths):
                            raise ValueError('Frame output conflicts with a queued source')
                        if not settings.destination.overwrite_existing and any(p.exists() for p in paths):
                            raise FileExistsError('One or more frame outputs already exist')
                        for frame, output in zip(document.frames, paths):
                            control.checkpoint()
                            export_document(output, document, settings.export, overwrite=settings.destination.overwrite_existing,
                                            cancel=control.cancelled.is_set, frame_ids={frame.id})
                            outputs.append(str(output))
                    else:
                        emit('phase', 'Encoding ' + item.output.name)
                        export_document(item.output, document, settings.export, overwrite=settings.destination.overwrite_existing,
                                        cancel=control.cancelled.is_set, frame_ids=ids)
                        outputs.append(str(item.output))
                    control.checkpoint()
                    message = ''
                    if settings.destination.delete_originals:
                        try:
                            item.source.unlink()
                        except OSError as exc:
                            message = f'Converted; original could not be deleted: {exc}'
                    record = FileResult(str(item.source), 'converted', tuple(outputs), message)
        except CancelledError:
            record = FileResult(str(item.source), 'cancelled', tuple(outputs), 'Cancelled; earlier completed outputs are retained')
            result.files.append(record)
            emit('result', record)
            for pending in plan[index+1:]:
                result.files.append(FileResult(str(pending.source), 'cancelled', message='Not started'))
            break
        except FileExistsError as exc:
            record = FileResult(str(item.source), 'skipped', tuple(outputs), str(exc))
        except Exception as exc:
            record = FileResult(str(item.source), 'failed', tuple(outputs), str(exc))
        result.files.append(record)
        emit('result', record)
        emit('progress', index+1, total, str(item.source))
    if settings.destination.log_file_path:
        try:
            Path(settings.destination.log_file_path).write_text(json.dumps({
                'counts': result.counts, 'discovery_errors': result.discovery_errors,
                'files': [vars(r) for r in result.files]}, indent=2), encoding='utf-8')
        except OSError as exc:
            result.discovery_errors.append(f'Could not write log: {exc}')
            emit('log', result.discovery_errors[-1])
    emit('finished', result)
    return result
