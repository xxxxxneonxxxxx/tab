from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from collections import defaultdict

from .config import MAX_FRET, STANDARD_TUNING
from .models import NoteEvent


def read_midi(data: bytes) -> list[NoteEvent]:
    import mido

    midi = mido.MidiFile(file=io.BytesIO(data))
    events: list[NoteEvent] = []
    active: dict[tuple[int, int], tuple[float, int, int | None]] = {}
    absolute = 0.0
    for message in midi:
        absolute += message.time
        if message.type == "note_on" and message.velocity:
            active[(message.channel, message.note)] = (absolute, message.velocity, message.channel)
        elif message.type in {"note_off", "note_on"} and (message.type == "note_off" or not message.velocity):
            started = active.pop((message.channel, message.note), None)
            if started:
                start, velocity, channel = started
                events.append(NoteEvent(message.note, start, max(0.01, absolute - start), velocity, channel))
    return sorted(events, key=lambda item: (item.start, item.pitch))


def read_musicxml(data: bytes) -> list[NoteEvent]:
    root = ET.fromstring(data)
    divisions = 1.0
    tempo = 120.0
    cursor = 0.0
    events: list[NoteEvent] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "divisions" and element.text:
            divisions = max(1.0, float(element.text))
        if element.tag.rsplit("}", 1)[-1] != "note":
            continue
        rest = element.find(".//{*}rest")
        duration_node = element.find(".//{*}duration")
        duration = float(duration_node.text or 0) / divisions if duration_node is not None else 1.0
        if rest is not None:
            cursor += duration * 60.0 / tempo
            continue
        step = element.findtext(".//{*}pitch/{*}step")
        octave = element.findtext(".//{*}pitch/{*}octave")
        alter = element.findtext(".//{*}pitch/{*}alter") or "0"
        if step and octave:
            pitch = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[step]
            events.append(NoteEvent(12 * (int(octave) + 1) + pitch + int(float(alter)), cursor, duration * 60.0 / tempo))
        cursor += duration * 60.0 / tempo
    return events


def _groups(events: list[NoteEvent]) -> list[list[NoteEvent]]:
    groups: list[list[NoteEvent]] = []
    for event in sorted(events, key=lambda item: (item.start, item.pitch)):
        if not groups or abs(event.start - groups[-1][0].start) > 0.012:
            groups.append([event])
        else:
            groups[-1].append(event)
    return groups


def _candidates(pitch: int) -> list[tuple[int, int]]:
    """Return (string, fret) positions for a MIDI pitch."""
    return [
        (string + 1, pitch - open_pitch)
        for string, open_pitch in enumerate(STANDARD_TUNING)
        if 0 <= pitch - open_pitch <= MAX_FRET
    ]


def _place_group(group: list[NoteEvent], previous: dict[int, int]) -> list[tuple[NoteEvent, int | None, int | None]]:
    """Choose one unique string per simultaneous note.

    This is deliberately our own small dynamic placement algorithm. The
    score prefers low fret positions, then prefers staying near the previous
    hand position, while never putting two notes of a chord on one string.
    """
    ordered = sorted(group, key=lambda event: event.pitch, reverse=True)
    best: tuple[float, list[tuple[NoteEvent, int, int]]] | None = None

    def visit(index: int, used: set[int], current: list[tuple[NoteEvent, int, int]], cost: float) -> None:
        nonlocal best
        if index == len(ordered):
            if best is None or cost < best[0]:
                best = (cost, current.copy())
            return
        event = ordered[index]
        positions = _candidates(event.pitch)
        if not positions:
            visit(index + 1, used, current, cost + 1000.0)
            return
        for string, fret in positions:
            if string in used:
                continue
            movement = abs(fret - previous.get(string, fret))
            visit(index + 1, used | {string}, current + [(event, string, fret)], cost + fret * 0.12 + movement * 0.45)

    visit(0, set(), [], 0.0)
    placed_by_event = {id(event): (string, fret) for event, string, fret in (best[1] if best else [])}
    return [(event, *placed_by_event.get(id(event), (None, None))) for event in group]


def _render_guitar_part(groups: list[list[tuple[NoteEvent, int | None, int | None]]]) -> str:
    """Render our own aligned six-string tab with measure separators."""
    if not groups:
        return ""
    # MIDI is read in seconds and the configured sources use the common
    # 120-BPM quarter-note grid. Keep the grid readable even when a source
    # has triplets or very short ornaments.
    measure_seconds = 2.0
    widths: list[int] = []
    for group in groups:
        widest = max((len(str(fret)) for _, _, fret in group if fret is not None), default=1)
        widths.append(max(3, widest + 1))
    lines = [[] for _ in range(6)]
    previous_measure = int(groups[0][0][0].start // measure_seconds)
    for group, width in zip(groups, widths):
        measure = int(group[0][0].start // measure_seconds)
        if measure != previous_measure:
            for line in lines:
                line.extend(["|", "-"])
            previous_measure = measure
        for line in lines:
            line.extend(["-"] * width)
        for _, string, fret in group:
            if string is None or fret is None:
                continue
            value = str(fret)
            start = len(lines[string - 1]) - width
            lines[string - 1][start:start + len(value)] = value
    labels = ["e", "B", "G", "D", "A", "E"]
    return "\n".join(f"{label}|" + "".join(line) + "|" for label, line in zip(labels, lines))


def events_to_tab(events: list[NoteEvent]) -> dict:
    if not events:
        return {"tuning": ["E4", "B3", "G3", "D3", "A2", "E2"], "events": [], "ascii": ""}

    # MIDI guitar arrangements commonly contain one channel per guitar.
    # Convert each channel independently instead of merging two performances
    # into artificial chords.
    by_channel: dict[int | None, list[NoteEvent]] = defaultdict(list)
    for event in events:
        by_channel[event.channel].append(event)
    parts = []
    for channel, part_events in sorted(by_channel.items(), key=lambda item: (item[0] is None, item[0] or 0)):
        grouped = _groups(part_events)
        previous: dict[int, int] = {}
        placed_groups = []
        for group in grouped:
            placed = _place_group(group, previous)
            placed_groups.append(placed)
            for _, string, fret in placed:
                if string is not None and fret is not None:
                    previous[string] = fret
        part_ascii = _render_guitar_part(placed_groups)
        part_output = []
        for group in placed_groups:
            for event, string, fret in group:
                part_output.append(dict(event.as_dict(), fret=fret, string=string))
        parts.append({"channel": channel, "ascii": part_ascii, "events": part_output})
    ascii_tab = "\n\n".join(
        (f"Guitar part {index + 1}" if len(parts) > 1 else "") + ("\n" if len(parts) > 1 else "") + part["ascii"]
        for index, part in enumerate(parts)
    )
    return {
        "tuning": ["E4", "B3", "G3", "D3", "A2", "E2"],
        "events": [event for part in parts for event in part["events"]],
        "parts": [{"channel": part["channel"], "ascii": part["ascii"]} for part in parts],
        "ascii": ascii_tab,
    }
