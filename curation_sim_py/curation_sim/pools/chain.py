class Chain:
    def __init__(self, initialBlockHeight: int=0):
        self.blockHeight = initialBlockHeight

    def sleep(self, blocks: int):
        self.blockHeight += blocks

    def step(self):
        self.blockHeight += 1
