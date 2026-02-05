import os

from tornado import web
from asyncio import sleep
from jinja2 import ChoiceLoader, FileSystemLoader

from jupyter_server.base.handlers import JupyterHandler, APIHandler
from jupyter_server.utils import url_path_join

from subprocess import Popen
from os import path


class SwanCustomEnvironmentsApiHandler(APIHandler):
    """API handler for creating custom environments"""

    # Path to the script used to create custom environments
    makenv_path = path.join(path.dirname(__file__), "scripts/makenv.sh")

    # Path to the file where the log of the makenv.sh script is written
    LOG_FILE = "/tmp/makenv.log"

    makenv_process = None

    @web.authenticated
    async def get(self):
        """
        Gets the arguments from the query string and runs the makenv.sh script with them.
        repository (str): The git URL or absolute unix path to the repository.
        builder (str): The builder used for creating the environment.
        builder_version (str): The version of the specified builder.
        nxcals (bool): Whether to include NXCALS and Spark extensions in the environment.
        """
        self.set_header("Content-Type", "text/event-stream")
        # makenv_process = SwanCustomEnvironmentsApiHandler.makenv_process
        
        # if makenv_process is None:
        #     makenv_process = self._launch_makenv()
        #     SwanCustomEnvironmentsApiHandler.makenv_process = makenv_process
        self.log.info("Launched makenv.sh script")
        await self._process_log_stream()
        self.finish()

    def _launch_makenv(self) -> Popen:
        """Launches the makenv.sh script as a subprocess."""
        repository = self.get_query_argument("repository", default="")
        builder = self.get_query_argument("builder", default="")
        builder_version = self.get_query_argument("builder_version", default="")
        nxcals = self.get_query_argument("nxcals", default="")

        arguments = ["--repository", repository, "--builder", builder]
        if builder_version:
            arguments.extend(("--builder_version", builder_version))
        if nxcals:
            arguments.append("--nxcals")

        with open(self.LOG_FILE, "w") as log_file:
            return Popen([self.makenv_path, *arguments], stdout=log_file, stderr=log_file)

    async def _process_log_stream(self) -> None:
        """Reads from the log file and streams output to the client."""
        for _ in range(30):  # Wait for the log file to be created, with a timeout of 30 seconds
            self.log.info("Send line to client")
            await self._send_line("foo bar")
            await sleep(1)
        # with open(self.LOG_FILE, "r") as log_file:
        #     while True:
        #         line = log_file.readline()
        #         if not line and makenv_process.poll() is not None:
        #             break  # Process finished, no more logs to read
        #         await self._send_line(line)

    async def _send_line(self, line: str) -> None:
        """Sends a line to the client"""
        if line:
            self.write(line)
            await self.flush()
        # force a yield so that we can have multiple concurrent executions of get,
        # e.g. from multiple tabs
        await sleep(0)


class SwanCustomEnvironmentsHandler(JupyterHandler):
    """Render the custom environment building view"""

    @web.authenticated
    async def get(self):
        self.write(
            self.render_template(
                "customenvs.html",
                page_title="Creating custom environment",
                hub_prefix="http://localhost:8000/"
            )
        )

def _load_jupyter_server_extension(serverapp):
    """
    A server extension that registers the custom environment building API and view
    """

    web_app = serverapp.web_app

    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    jinja_env = web_app.settings["jinja2_env"]
    jinja_env.loader = ChoiceLoader([
        FileSystemLoader(templates_dir),
        jinja_env.loader,
    ])

    new_handlers = [
        (r"/api/customenvs", SwanCustomEnvironmentsApiHandler),
        (r"/customenvs", SwanCustomEnvironmentsHandler),
    ]

    for handler in new_handlers:
        pattern = url_path_join(web_app.settings["base_url"], handler[0])
        new_handler = tuple([pattern] + list(handler[1:]))
        web_app.add_handlers(".*$", [new_handler])
