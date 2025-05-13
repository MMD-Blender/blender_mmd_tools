from __future__ import print_function

import argparse
import io
import sys

from opencc import OpenCC


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--input', metavar='<file>',
                        help='Read original text from <file>.')
    parser.add_argument('-o', '--output', metavar='<file>',
                        help='Write converted text to <file>.')
    parser.add_argument('-c', '--config', metavar='<conversion>',
                        help='Conversion')
    parser.add_argument('--in-enc', metavar='<encoding>', default='UTF-8',
                        help='Encoding for input')
    parser.add_argument('--out-enc', metavar='<encoding>', default='UTF-8',
                        help='Encoding for output')
    args = parser.parse_args()

    if args.config is None:
        print("Please specify a conversion.", file=sys.stderr)
        return 1

    cc = OpenCC(args.config)

    if args.input:
        with io.open(args.input, encoding=args.in_enc) as f:
            input_str = f.read()
    else:
        input_str = sys.stdin.read()

    output_str = cc.convert(input_str)

    if args.output:
        with io.open(args.output, "w", encoding=args.out_enc) as f:
            f.write(output_str)
    else:
        sys.stdout.write(output_str)

    return 0


if __name__ == '__main__':
    sys.exit(main())
