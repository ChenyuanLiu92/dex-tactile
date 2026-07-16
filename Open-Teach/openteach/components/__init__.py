from .component import Component


def __getattr__(name):
    if name in {'RealsenseCameras', 'TeleOperator', 'Collector'}:
        from .initializers import Collector, RealsenseCameras, TeleOperator
        return {'RealsenseCameras': RealsenseCameras, 'TeleOperator': TeleOperator, 'Collector': Collector}[name]
    raise AttributeError(name)
