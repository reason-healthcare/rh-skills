import click
from rh_skills.commands import (
    ingest,
    init,
    list_cmd,
    promote,
    schema,
    search,
    skills,
    status,
    tasks,
    test_cmd,
    validate,
)


@click.group()
def main():
    """RH Skills CLI for informatics workflows."""
    pass


main.add_command(init.init)
main.add_command(status.status)
main.add_command(list_cmd.list_)
main.add_command(promote.promote)
main.add_command(schema.schema)
main.add_command(validate.validate)
main.add_command(ingest.ingest)
main.add_command(tasks.tasks)
main.add_command(test_cmd.test)
main.add_command(search.search)
main.add_command(skills.skills)
