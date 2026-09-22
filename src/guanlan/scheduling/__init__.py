"""Single-caller, single-view latest-first pending work slot."""


class LatestFirst:
    def __init__(self):
        self.active = None
        self.pending = None

    def submit(self, request):
        if request is None:
            raise ValueError("request cannot be None")
        self.pending = request

    def start(self):
        if self.active is not None:
            raise RuntimeError("finish the active request before starting another")
        self.active, self.pending = self.pending, None
        return self.active

    def finish(self):
        if self.active is None:
            raise RuntimeError("no active request to finish")
        completed, self.active = self.active, None
        return completed
