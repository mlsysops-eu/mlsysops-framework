import asyncio
import json

import fita

queue_inbound = asyncio.Queue()
queue_outbound = asyncio.Queue()

async def tester_listener():
    while True:
        message = await queue_inbound.get()

        print(message)

async def main():

    asyncio.create_task(tester_listener())
    fita.initialize(inbound_queue= queue_outbound, outbound_queue= queue_inbound)

    print("Going into loop")
    #Loop forever
    while True:
        try:
            await asyncio.sleep(10)
            print("Applying control knob")
            fita.apply({"event":"CONTROL_KNOB_EVENT","payload":{"control_knob":"TX_PWR","action":"SET","value":"MED"}})
        except KeyboardInterrupt:
            break

if __name__ ==  '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())