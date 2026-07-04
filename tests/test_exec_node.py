import asyncio

from exec_node import exec_code


def test_exec_code_executes_python_script_with_main():
    result = asyncio.run(exec_code("def main():\n    return 7 * 2\n"))

    assert result == 14
