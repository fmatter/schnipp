"""Console script for schnipp."""
import sys
import click
from pathlib import Path

# https://stackoverflow.com/questions/52053491/a-command-without-name-in-click
# from click_default_group import DefaultGroup
from schnipp import schnipp
import logging

log_lvl = logging.INFO
logging.getLogger("schnipp").setLevel(log_lvl)
log = logging.getLogger(__name__)

log.info("CLI init")


def listify(x):
    if not x:
        return []
    if not isinstance(x, list):
        return [x]
    return x


@click.command()
@click.argument("audio", required=False, default=None,    type=click.Path(exists=True, path_type=Path),
)
@click.argument("metadata", required=False, default=None,    type=click.Path(exists=True, path_type=Path),
)
@click.option("-a", "--audio", "add_audio", default=None)
@click.option("-m", "--metadata", "add_meta", default=None)
@click.option(
    "-o",
    "--output",
    "output_dir",
    default=None,
    type=click.Path(exists=True, path_type=Path),
)
def main(audio, metadata, add_audio, add_meta, output_dir):
    """(default) segment audio file into snippets"""
    audio, metadata, add_audio, add_meta = (
        listify(v) for v in [audio, metadata, add_audio, add_meta]
    )
    audio.extend(add_audio)
    metadata.extend(add_meta)
    if not output_dir:
        output_dir = audio[0].parents[0]
    if not audio or not metadata:
        log.error("Please specify one or multiple metadata and audio files:")
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        ctx.exit()
    else:
        schnipp(audio, metadata, output_dir, col_names={"start_key": "Start", "end_key": "End"})
    pass


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover

# @main.command()
# @click.argument("src")
# @click.argument("target")
# @click.option(
#     "-a",
#     "--text-abbr",
#     default=None,
#     help="Text abbreviation / ID to be used; if empty, the first text will be used.",
# )
# @click.option("-o", "--out-dir", default=Path("./audio"), help="Where to export audio snippets to.")
# @click.option("-f", "--export-format", default="wav", help="Exported audio format.")
# @click.option("-s", "--slugify", default=False, help="Slugify filenames.")
# @click.option("-t", "--tier", multiple=True, help="ELAN tiers.")
# def convert(
#     src, target, out_dir, text_abbr, export_format, slugify, tier
# ):  # pylint: disable=too-many-arguments
#     """Extract audio snippets from audio file <TARGET> based on file with time codes <SRC>."""
#     process_file(
#         filename=src,
#         audio_file=target,
#         out_dir=out_dir,
#         text_abbr=text_abbr,
#         export_format=export_format,
#         slugify_abbr=slugify,
#         tiers=tier,
#     )
