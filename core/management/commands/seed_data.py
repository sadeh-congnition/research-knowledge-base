import djclick as click
from core.models import Project, Node


@click.command()
def command():
    # Clear existing data
    Project.objects.all().delete()

    p1 = Project.objects.create(
        name="Quantum Physics Research", description="Exploring quantum entanglement."
    )
    n1 = Node.objects.create(
        project=p1,
        title="Entanglement",
        content="A physical phenomenon that occurs when a group of particles are generated, interact, or share spatial proximity in a way such that the quantum state of each particle of the group cannot be described independently of the state of the others.",
    )
    n2 = Node.objects.create(
        project=p1,
        title="Bell's Theorem",
        content="A theorem that shows that no local hidden variable theory can reproduce all the predictions of quantum mechanics. See [[Entanglement]].",
    )

    n2.links.add(n1)

    click.echo(f"Created project: {p1.name}")
    click.echo(f"Created node: {n1.title}")
    click.echo(f"Created node: {n2.title}")
