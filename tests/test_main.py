from project_course.main import build_status_message


def test_build_status_message() -> None:
    assert build_status_message() == "project-course scaffold ready"
