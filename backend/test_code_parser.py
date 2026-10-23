
from app.services.code_parser import PythonCodeParser


sample_code = '''
from fastapi import FastAPI
import os


class UserService:
    def get_user(self, user_id):
        return user_id


async def create_user(name, email):
    return {"name": name, "email": email}
'''


def test_python_code_parser():
    result = PythonCodeParser.parse(sample_code)

    assert result["success"] is True
    assert len(result["classes"]) == 1
    assert result["classes"][0]["name"] == "UserService"
    assert len(result["functions"]) == 2
    assert len(result["imports"]) == 2

    print("Classes:")
    for item in result["classes"]:
        print(f"  {item['name']} (line {item['line']})")

    print("\nFunctions:")
    for item in result["functions"]:
        print(
            f"  {item['name']} "
            f"(line {item['line']}, async={item['is_async']})"
        )

    print("\nImports:")
    for item in result["imports"]:
        print(f"  {item['kind']}: {item['module']}")

    print("\nPython parser test passed!")


if __name__ == "__main__":
    test_python_code_parser()
