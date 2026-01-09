import argparse
import os.path

from .mock_recorder import testConfigUi, FAKE_RECORDER

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='CONFIG.UI Rendering Tester')
    parser.add_argument('configUi',
                        help="CONFIG.UI data, either XML or EBML. "
                             "'default' to use the fake recorder's CONFIG.UI file.")
    parser.add_argument('-p', '--path', default=os.path.abspath(FAKE_RECORDER),
                        help='Path to a base fake recorder directory. '
                             f'Defaults to {os.path.abspath(FAKE_RECORDER)}')
    args = parser.parse_args()
    configUi = None if args.configUi == 'default' else args.configUi

    print('To reload the CONFIG.UI, hold Ctrl+Shift and click Cancel.')
    testConfigUi(configUi, path=args.path)
