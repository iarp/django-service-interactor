
class Base(object):
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return self.__dict__


class Calendar(Base):
    id = None
    name = None
    link = None
    primary = None

    can_edit = False

    raw = None


class CalendarEvent(Base):
    id = None
    calendar_id = None
    name = None
    link = None
    start = None
    end = None
    location = None
    description = None

    raw = None
