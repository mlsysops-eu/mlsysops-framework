import spade

class DummyAgent(spade.agent.Agent):
    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))

async def main():
    dummy = DummyAgent("admin@10.96.82.195", "1234")
    await dummy.start()

if __name__ == "__main__":
    spade.run(main())
