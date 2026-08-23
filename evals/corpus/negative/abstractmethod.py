import abc

class Worker(abc.ABC):
    @abc.abstractmethod
    def run(self):
        pass
