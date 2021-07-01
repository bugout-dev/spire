import argparse


class GitHubArgumentParseError(Exception):
    """
    Raised when there is an error parsing arguments for a CLI invocation from GitHub.
    """


class CustomHelpAction(argparse._HelpAction):
    """
    Custom argparse action that handles -h and --help flags in Bugout Slack argument parsers.
    This is part of the dirty hack to get around the annoying exit behaviour of argparse. The other
    part of this is the custom ArgumentParser subclass we use (defined below).
    """

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help=None,
    ):
        super().__init__(option_strings, dest, default, help)

    def __call__(self, parser, namespace, values, option_string=None):
        raise GitHubArgumentParseError(parser.format_help())


class BugoutGitHubArgumentParser(argparse.ArgumentParser):
    """
    Parser for CLI invocations via GitHub.

    Modified version of parse_raw_text() from slack/commands.py
    """

    def error(self, message):
        message_with_usage = f"{self.format_usage()}\n{message}"
        raise GitHubArgumentParseError(message_with_usage)

    def register(self, registry_name, value, object):
        registry = self._registries.setdefault(registry_name, {})
        if value == "help":
            registry[value] = CustomHelpAction
        else:
            registry[value] = object
