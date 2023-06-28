"""Top-level package for schnipp."""
import sys
from pathlib import Path
from xml.etree import ElementTree
from pydub import AudioSegment
import csv
from humidifier import humidify

import logging
import colorlog


handler = colorlog.StreamHandler(None)
handler.setFormatter(
    colorlog.ColoredFormatter("%(log_color)s%(levelname)-7s%(reset)s %(message)s")
)
log = logging.getLogger(__name__)
log.propagate = True
log.addHandler(handler)


__author__ = "Florian Matter"
__email__ = "fmatter@mailbox.org"
__version__ = "0.0.1.dev"


def get_slice(audio, target_file, start, end, export_format="wav"):
    if not isinstance(start, float) or not isinstance(end, float):
        log.warning("Missing time information")
        log.warning(target_file)
        return None
    if not Path(target_file).is_file():
        print(start, end)
        segment = audio[int(start) : int(end)]
        segment.export(target_file, format=export_format)
    else:
        log.info(f"File {target_file} already exists")


def load_file(file_path, audio_format="wav"):
    if audio_format == "wav":
        return AudioSegment.from_wav(file_path)
    log.error(f"{audio_format} files are not yet supported.")
    sys.exit()


def cut_file(
    file,
    records,
    output_dir,
    id_key="ID",
    start_key="Start",
    end_key="End",
):
    file = Path(file)
    output_dir = Path(output_dir)
    audio = load_file(file)
    for rec in records:
        if not rec[start_key] or not rec[end_key]:
            continue
        if rec["Filename"] == file.name:
            get_slice(
                audio,
                output_dir / (rec[id_key] + ".wav"),
                float(rec[start_key]),
                float(rec[end_key]),
            )
        else:

            pass
            # print("NO", rec["ID"])


def load_records(metadata_files, input_dir="."):
    input_dir = Path(input_dir)
    out = []
    for f in metadata_files:
        f = input_dir / f
        if f.suffix == ".csv":
            with open(f, newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    if "Filename" not in row:
                        row["Filename"] = f.stem
                    out.append(row)
        elif f.suffix == ".flextext":
            out.extend(from_flextext(f))
    return out


def dfy(recs):
    import pandas as pd

    return pd.DataFrame.from_dict(recs)


def schnipp(
    audio_files,
    metadata_files,
    output_dir,
    text_filename_dict=None,
    col_names={},
    time_unit="ms",
    offset=0,
):
    records = load_records(metadata_files)
    unit_identifier = col_names.get("unit_identifier", "Text_ID")
    for rec in records:
        print(rec)
        for key in [col_names["start_key"], col_names["end_key"]]:
            if rec[key] != "":
                if time_unit == "s":
                    rec[key] = float(rec[key]) * 1000 + offset
                else:
                    rec[key] = float(rec[key]) + offset
    if not text_filename_dict:
        if len(audio_files) == 1:
            log.warning(
                f"Assuming that all records in {', '.join([Path(x).name for x in metadata_files])} refer to {audio_files[0]}"
            )
            for rec in records:
                rec["Filename"] = Path(audio_files[0]).name
        else:
            log.error("Not yet implemented")
            sys.exit()
    else:
        for rec in records:
            rec["Filename"] = text_filename_dict.get(
                rec[unit_identifier], rec.get("Filename", None)
            )
    for file in audio_files:
        cut_file(file, records, output_dir, **col_names)
    df = dfy(records)


def get_text_abbr(text):
    for item in text.iter("item"):
        if item.attrib["type"] == "title-abbreviation":
            return item.text
    return ""


def get_media_url(elan_file, tree):
    for media_file in tree.iter("MEDIA_DESCRIPTOR"):
        media_url = media_file.attrib["RELATIVE_MEDIA_URL"]
        if ".wav" in media_url:
            return Path(elan_file).parents[0] / media_url
    return None


def from_elan(elan_file, tiers, text_abbr, audio_file, **kwargs):
    del kwargs
    if len(tiers) == 0:
        raise ValueError("Specify at least 1 tier.")
    tree = ElementTree.parse(elan_file)
    timeslots = {}
    for ts in tree.iter("TIME_SLOT"):
        timeslots[ts.attrib["TIME_SLOT_ID"]] = ts.attrib["TIME_VALUE"]
    audio_file = audio_file or get_media_url(elan_file, tree)
    audio = load_file(audio_file)
    for tier in tiers:
        c = 0
        for entry in tree.find(f"""TIER[@TIER_ID='{tier}']"""):
            annot = entry.find("ALIGNABLE_ANNOTATION")
            c += 1
            aid = entry.find("ALIGNABLE_ANNOTATION").get(
                "ANNOTATION_ID",
                {annot.attrib["TIME_SLOT_REF1"]} - {annot.attrib["TIME_SLOT_REF2"]},
            )
            get_slice(
                audio,
                f"{text_abbr}-{c}.wav",
                float(timeslots[annot.attrib["TIME_SLOT_REF1"]]),
                float(timeslots[annot.attrib["TIME_SLOT_REF2"]]),
            )


def from_flextext(
    flextext_file,
    out_dir=".",
    text_abbr=None,
    id_func=None,
    slugify_abbr=False,
    export_format="wav",
):  # pylint: disable=too-many-arguments,too-many-locals
    """Args:
        flextext_file (str): Path to a .flextext file.
        out_dir (str): Path to the folder where snippets are exported to (default: ``.``).
        text_abbr: What to look for in ``title-abbreviation`` field. If empty, the first text in the file will be used.
        id_func: If you want something other than the FLEx ``segnum`` field.
        slugify_abbr: Whether to slugify text abbreviations (default: ``False``).
        export_format (str): The format to export snippets to (default: ``wav``).

    Returns:
        None"""
    log.debug(flextext_file)
    out_dir = Path(out_dir)
    if not id_func:

        def id_func(phrase, abbr, sep="-", backup_no=1):
            for item in phrase.iter("item"):
                return humidify(abbr + sep + item.text)
            return f"{abbr}{sep}{backup_no}"

    if not Path(flextext_file).is_file():
        raise ValueError("Please provide a path to a valid source file (.flextext)")

    log.debug("Loading XML")
    tree = ElementTree.parse(flextext_file)
    log.debug("Iterating texts")
    records = []
    for text in tree.iter("interlinear-text"):
        good = False
        if text_abbr:
            title_abbr = get_text_abbr(text)
            log.debug(title_abbr)
            if title_abbr == text_abbr:
                log.info(f"Hit: {text_abbr}")
                good = True
            elif not text_abbr:
                log.warning("Found text with no title-abbreviation.")
        else:
            log.info(f"Parsing , using first text in {flextext_file}")
            good = True
            text_abbr = get_text_abbr(list(tree.iter("interlinear-text"))[0])
        if slugify_abbr:
            text_abbr = humidify(text_abbr)
        if good:
            for i, phrase in enumerate(text.iter("phrase")):
                phrase_id = id_func(phrase, text_abbr, backup_no=i)
                if "begin-time-offset" not in phrase.attrib:
                    raise ValueError(
                        f"Phrase {phrase_id} in {text_abbr} in {flextext_file} has no [begin-time-offset] value."
                    )
                start = int(phrase.attrib["begin-time-offset"])
                end = int(phrase.attrib["end-time-offset"])
                records.append(
                    {"ID": phrase_id, "Text_ID": text_abbr, "Start": start, "End": end}
                )
    return records
