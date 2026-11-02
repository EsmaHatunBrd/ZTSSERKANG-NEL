import pytest
from backend.depo.veritabani import Base, motor_olustur, oturum_fabrikasi


@pytest.fixture
def oturum():
    engine = motor_olustur("sqlite://")
    Base.metadata.create_all(engine)
    s = oturum_fabrikasi(engine)()
    yield s
    s.close()
