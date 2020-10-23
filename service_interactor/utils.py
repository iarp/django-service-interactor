import datetime

import dateutil.parser


def get_takeout_files(provider, include_details=True, allow_over_10mb=False):
    files = {}
    this_yearmonth = datetime.datetime.now().strftime('%Y%m')

    # Only zip files and files dated this year and month at minimum
    for file in provider.get_files(
            orderBy='createdTime desc',
            q=f"mimeType='application/x-zip' and name contains 'takeout-{this_yearmonth}'"
    ):

        if include_details:
            try:
                details = provider.get_file_details(file_id=file['id'], fields='size,createdTime')
                file['created'] = dateutil.parser.parse(details['createdTime'])
                file['size'] = round(int(details.get('size')) / 1000 / 1000, 2)
            except:  # noqa
                file['created'] = None
                file['size'] = None

            if not allow_over_10mb and file['size'] and file['size'] > 10.0:
                continue

        files[file['id']] = file

    return files
