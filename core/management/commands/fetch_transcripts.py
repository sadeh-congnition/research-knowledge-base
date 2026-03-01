import time
import re
import djclick as click
from core.models import Node
from youtube_transcript_api import YouTubeTranscriptApi

YOUTUBE_RE = re.compile(
    r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
)


@click.command()
def command():
    """Fetch YouTube video transcripts for each Node and append to content."""
    nodes = Node.objects.all()
    count = 0

    click.echo(f"Found {nodes.count()} nodes in the database. Processing...")

    for node in nodes:
        # Avoid processing if transcript is already appended
        if "Transcript:" in node.content:
            click.echo(
                f"Skipping '{node.title}' - transcript already appears to be present."
            )
            continue

        match = YOUTUBE_RE.search(node.content)
        if not match:
            # Check title just in case the URL was put there
            match = YOUTUBE_RE.search(node.title)

        if match:
            video_id = match.group(1)
            click.echo(
                f"Fetching transcript for video ID '{video_id}' (Node: '{node.title}')..."
            )

            try:
                transcript_list = YouTubeTranscriptApi().list(video_id)
                transcript = transcript_list.find_transcript(["en"])
                fetched_transcript = transcript.fetch()

                # Format to a plain text string
                text_formatted = "\n".join(
                    [
                        x["text"] if isinstance(x, dict) else x.text
                        for x in fetched_transcript
                    ]
                )

                node.content += f"\n\nTranscript:\n{text_formatted}"
                node.save()
                click.secho(
                    f"Successfully appended transcript to '{node.title}'.", fg="green"
                )
                count += 1

                # Sleep 5 seconds after processing successfully as requested
                click.echo("Sleeping for 5 seconds...")
                time.sleep(5)
            except Exception as e:
                click.secho(
                    f"Failed to fetch transcript for '{node.title}': {e}", fg="red"
                )
        else:
            click.echo(f"No YouTube URL found for '{node.title}'.")

    click.secho(f"\nProcessing complete. Updated {count} nodes.", fg="green", bold=True)
