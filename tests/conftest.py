import os


def pytest_sessionstart(session):
    os.environ["ENV"] = "TEST"