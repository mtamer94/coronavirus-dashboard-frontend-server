#!/usr/bin python3

# Imports
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Python:
import logging
from operator import itemgetter

# 3rd party:
from flask import render_template, request, g, Blueprint

# Internal: 
from ..common.data.queries import (
    get_data_by_postcode,
    get_msoa_data, get_r_values, get_alert_level,
    get_postcode_areas, latest_rate_by_metric
)

from .utils import get_validated_postcode, get_card_data
from ..common.utils import get_main_data, get_notification_content

try:
    from __app__.database import CosmosDB
    from __app__.storage import StorageClient
except ImportError:
    from database import CosmosDB
    from storage import StorageClient

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

__all__ = [
    'postcode_page'
]

postcode_page = Blueprint('postcode_page', __name__)

get_area_type = itemgetter("areaType")


def get_by_smallest_areatype(items, areatype_getter):
    order = [
        "lsoa",
        "msoa",
        "ltla",
        "utla",
        "region",
        "nhsRegion",
        "nation",
        "overview"
    ]
    area_types = map(areatype_getter, items)

    min_index = len(order) - 1
    result = None

    for item_ind, area_type in enumerate(area_types):
        order_index = order.index(area_type['abbr'])
        if area_type['abbr'] in order and order_index < min_index:
            result = items[item_ind]
            min_index = order_index

    return result


@postcode_page.route('/search')
def postcode_search() -> render_template:
    postcode = get_validated_postcode(request.args)

    data = get_main_data(g.timestamp)

    if postcode is None:
        return render_template(
            "main.html",
            changelog = get_notification_content(g.timestamp),
            invalid_postcode=True,
            r_values=get_r_values(g.timestamp),
            cases_rate=latest_rate_by_metric(g.timestamp, "newCasesBySpecimenDate"),
            deaths_rate=latest_rate_by_metric(g.timestamp, "newDeaths28DaysByDeathDate"),
            admissions_rate=latest_rate_by_metric(g.timestamp, "newAdmissions"),
            **data
        )

    try:
        response = {
            category: {
                **values,
                **get_card_data(g.timestamp, values["metric"], values['data'], False, postcode)
            }
            for category, values in get_data_by_postcode(postcode, g.timestamp).items()
        }
    except IndexError as err:
        logging.exception(err)
        return render_template(
            "main.html",
            changelog = get_notification_content(g.timestamp),
            invalid_postcode=True,
            r_values=get_r_values(g.timestamp),
            cases_rate=latest_rate_by_metric(g.timestamp, "newCasesBySpecimenDate"),
            deaths_rate=latest_rate_by_metric(g.timestamp, "newDeaths28DaysByDeathDate"),
            admissions_rate=latest_rate_by_metric(g.timestamp, "newAdmissions"),
            **data
        )

    postcode_data = get_postcode_areas(postcode)

    healthcare_region = postcode_data['nhsRegionName']
    if healthcare_region is None:
        healthcare_region = postcode_data['nationName']

    return render_template(
        "postcode_results.html",
        changelog = get_notification_content(g.timestamp),
        postcode_data=response,
        postcode=postcode.upper(),
        area_info=postcode_data,
        cases_rate=latest_rate_by_metric(g.timestamp, "newCasesBySpecimenDate", True, postcode),
        admissions_rate=latest_rate_by_metric(g.timestamp, "newAdmissions", True, postcode),
        r_values=get_r_values(g.timestamp, healthcare_region),
        smallest_area=get_by_smallest_areatype(list(response.values()), get_area_type),
        alert_level=get_alert_level(postcode, g.timestamp),
        msoa=get_msoa_data(postcode, g.timestamp),
        **data
    )
