import logging

try:
    from IPython.display import HTML, display
except ImportError:
    IPython = None

try:
    from ipywidgets import widgets as widgets
except ImportError:
    widgets = None


class HTMLFormatter(logging.Formatter):
    """
    Prettily formats logs. Could use rich, too.
    From: https://stackoverflow.com/questions/68807282/rich-logging-output-in-jupyter-ipython-notebook
    """

    level_colors = {
        logging.DEBUG: "lightblue",
        logging.INFO: "dodgerblue",
        logging.WARNING: "goldenrod",
        logging.ERROR: "crimson",
        logging.CRITICAL: "firebrick",
    }

    def __init__(self):
        super().__init__(
            '<span style="font-weight: bold; color: green">{asctime}</span> '
            '[<span style="font-weight: bold; color: {levelcolor}">{levelname}</span>] '
            "{message}",
            style="{",
        )

    def format(self, record):
        record.levelcolor = self.level_colors.get(record.levelno, "black")
        return HTML(super().format(record))


class JupyterLoggingHandler(logging.Handler):
    """Custom logging handler sending logs to an output widget"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = {
            "width": "100%",
        }
        self.setFormatter(HTMLFormatter())
        self.out = widgets.Output(layout=layout)

    def emit(self, record):
        """Overload of logging.Handler method"""
        formatted_record = self.format(record)
        self.out.append_display_data(formatted_record)

    def show_logs(self):
        """Show the logs"""
        display(self.out)

    def clear_logs(self):
        """Clear the current logs"""
        self.out.clear_output()


class IPythonLoggingHandler(logging.Handler):
    """Custom logging handler sending logs to an output widget"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFormatter(HTMLFormatter())

    def emit(self, record):
        message = self.format(record)
        display(message)


class JupyterLogger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from IPython.display import HTML, display

        self.handler = JupyterLoggingHandler()
        self.addHandler(self.handler)

    def show(self):
        display(self.handler.out)


class IPythonLogger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handler = IPythonLoggingHandler()
        self.addHandler(self.handler)


class RegularLogger(logging.Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handler = logging.StreamHandler()
        self.addHandler(self.handler)


def create_logger(name, settings, log_level=logging.INFO):
    if settings.interpreter.jupyter:
        logger = JupyterLogger(name)

    elif settings.interpreter.ipython:
        logger = IPythonLogger(name)

    else:
        logger = RegularLogger(name)

    logger.setLevel(log_level)
    return logger
