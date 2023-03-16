import json


def json_out(json_str: str) -> dict | list:
    return json.loads(json_str)


print("Some json for you", json_out('{"Hello": "JSON"}'))

some_text = "THIS IS A REALLY LONG STRING ON ONE LINE. THIS IS A REALLY LONG STRING ON ONE LINE. THIS IS A REALLY LONG STRING ON ONE LINE. THIS IS A REALLY LONG STRING ON ONE LINE. THIS IS A REALLY LONG STRING ON ONE LINE."  # noqa
