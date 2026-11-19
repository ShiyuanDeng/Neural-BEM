"""Compare the owned TM path with the pinned upstream two-receiver path."""
from .check_table import launch_check
from .inputs import arguments


if __name__ == '__main__':
    args = arguments(__doc__, forward=True)
    launch_check(args.run_dir, args.case, 'clean', 'equivalence', 'native_equivalence_check',
                 record_name='equivalence_upstream')
