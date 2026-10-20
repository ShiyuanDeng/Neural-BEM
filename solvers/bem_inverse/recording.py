"""Optional observation hooks; records never provide numerical decisions."""
def observe(physics, kind, **record):
    """Optional immutable-evidence hook; the observer cannot supply decisions."""
    observer = getattr(physics, 'observer', None)
    if observer is not None:
        observer(kind, record)
