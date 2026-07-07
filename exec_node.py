import json


async def exec_code(script: str):
    namespace = {"__name__": "__main__"}
    exec(compile(script, "<lotsonet_script>", "exec"), namespace, namespace)

    main_fn = namespace.get("main")
    if callable(main_fn):
        return main_fn()
    return None


def serialize_value(value):
    if isinstance(value, (int, float, bool, str, bytes)):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)
