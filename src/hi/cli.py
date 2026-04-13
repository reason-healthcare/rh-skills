import click
from hi.commands import init, status, list_cmd, promote, validate, ingest, tasks, test_cmd, search, skills


@click.group()
def main():
    """RH Skills CLI for informatics workflows."""
    pass


main.add_command(init.init)
main.add_command(status.status)
main.add_command(list_cmd.list_)
main.add_command(promote.promote)
main.add_command(validate.validate)
main.add_command(ingest.ingest)
main.add_command(tasks.tasks)
main.add_command(test_cmd.test)
main.add_command(search.search)
main.add_command(skills.skills)
