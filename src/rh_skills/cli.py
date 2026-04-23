import click
from rh_skills.commands import (
    cql as cql_cmd,
    formalize,
    formalize_config,
    ingest,
    init,
    list_cmd,
    package,
    promote,
    render,
    schema,
    search,
    skills,
    source,
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
main.add_command(formalize.formalize)
main.add_command(formalize_config.formalize_config)
main.add_command(package.package)
main.add_command(schema.schema)
main.add_command(source.source)
main.add_command(validate.validate)
main.add_command(render.render)
main.add_command(ingest.ingest)
main.add_command(tasks.tasks)
main.add_command(test_cmd.test)
main.add_command(search.search)
main.add_command(skills.skills)
main.add_command(cql_cmd.cql)
