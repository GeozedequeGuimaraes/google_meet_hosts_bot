from src.infrastructure.google.meet_gateway import extrair_codigos_meet, resolver_nome_do_space_com_servico


class _FakeExecute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeSpaces:
    def __init__(self, payload):
        self.payload = payload
        self.requested_names = []

    def get(self, name):
        self.requested_names.append(name)
        return _FakeExecute(self.payload)


class _FakeMeetService:
    def __init__(self, payload):
        self._spaces = _FakeSpaces(payload)

    def spaces(self):
        return self._spaces


def test_extracts_meet_codes_from_conference_data_and_url():
    event = {
        "conferenceData": {
            "conferenceId": "abc-defg-hij",
            "entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/xyz-wxyz-abc"}],
        }
    }

    assert extrair_codigos_meet(event) == ["abc-defg-hij", "xyz-wxyz-abc"]


def test_resolves_canonical_space_name_with_service():
    event = {"conferenceData": {"conferenceId": "abc-defg-hij"}}
    service = _FakeMeetService({"name": "spaces/canonical-space"})

    assert resolver_nome_do_space_com_servico(service, event) == "spaces/canonical-space"
    assert service._spaces.requested_names == ["spaces/abc-defg-hij"]


def test_resolves_candidate_without_service_for_unit_paths():
    event = {"conferenceData": {"conferenceId": "abc-defg-hij"}}

    assert resolver_nome_do_space_com_servico(None, event) == "spaces/abc-defg-hij"
