import argparse
import json
from pathlib import Path
from fitness.pipeline import connect, ingest, refresh, refresh_incremental, erase_user


def main():
    parser=argparse.ArgumentParser(description='Synthetic fitness data pipeline')
    parser.add_argument('--database',default='fitness.db')
    commands=parser.add_subparsers(dest='command',required=True)
    load=commands.add_parser('ingest');load.add_argument('file')
    summary=commands.add_parser('summarize');summary.add_argument('--as-of',required=True);summary.add_argument('--incremental',action='store_true')
    delete=commands.add_parser('erase');delete.add_argument('user_id')
    args=parser.parse_args()
    with connect(args.database) as conn:
        if args.command=='ingest':
            records=[json.loads(line) for line in Path(args.file).read_text().splitlines() if line.strip()]
            result=ingest(conn,records)
        elif args.command=='summarize':result=(refresh_incremental if args.incremental else refresh)(conn,args.as_of)
        else:result=erase_user(conn,args.user_id)
    print(json.dumps(result,indent=2,allow_nan=False))


if __name__=='__main__':main()
