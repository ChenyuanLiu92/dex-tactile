from openteach.robot.inspire.hand import InspireHand


class Response:
    def __init__(self, registers=None):
        self.registers = registers or []

    def isError(self):
        return False


class FakeModbusClient:
    def __init__(self):
        self.writes = []
        self.closed = False

    def connect(self):
        return True

    def close(self):
        self.closed = True

    def read_holding_registers(self, address, count):
        return Response([1000, 900, 800, 700, 600, 500])

    def write_registers(self, address, values):
        self.writes.append((address, list(values)))
        return Response()


def test_real_hand_reads_and_writes_six_inspire_channels():
    client = FakeModbusClient()
    hand = InspireHand(host='192.0.2.11', dry_run=False, client_factory=lambda *_: client)

    assert hand.get_joint_position().tolist() == [1000, 900, 800, 700, 600, 500]
    hand.move([900, 800, 700, 600, 500, 400])

    assert client.writes == [
        (1522, [120] * 6),
        (1498, [500] * 6),
        (1486, [900, 800, 700, 600, 500, 400]),
    ]


def test_dry_run_never_connects_or_writes():
    hand = InspireHand(host='192.0.2.11', dry_run=True, client_factory=lambda *_: (_ for _ in ()).throw(AssertionError('connected')))
    hand.move([900] * 6)
    assert hand.get_joint_position().tolist() == [900] * 6


def test_hand_accepts_per_channel_force_and_dynamic_speed():
    client = FakeModbusClient()
    hand = InspireHand(
        host='192.0.2.11',
        dry_run=False,
        force=[220, 120, 120, 120, 220, 220],
        client_factory=lambda *_: client,
    )

    hand.move([900] * 6, speed=[30, 30, 80, 80, 160, 160])

    assert client.writes == [
        (1522, [30, 30, 80, 80, 160, 160]),
        (1498, [220, 120, 120, 120, 220, 220]),
        (1486, [900] * 6),
    ]


def test_hand_only_rewrites_speed_and_force_when_they_change():
    client = FakeModbusClient()
    hand = InspireHand(
        host='192.0.2.11',
        dry_run=False,
        speed=30,
        force=[220, 120, 120, 120, 220, 220],
        client_factory=lambda *_: client,
    )

    hand.move([900] * 6)
    hand.move([850] * 6)
    hand.move([800] * 6, speed=[30, 30, 80, 80, 160, 160])

    assert client.writes == [
        (1522, [30] * 6),
        (1498, [220, 120, 120, 120, 220, 220]),
        (1486, [900] * 6),
        (1486, [850] * 6),
        (1522, [30, 30, 80, 80, 160, 160]),
        (1486, [800] * 6),
    ]
