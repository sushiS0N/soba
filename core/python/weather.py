# load epw weather data
from ladybug.epw import EPW
from ladybug.location import Location
from ladybug.sunpath import Sunpath
import ladybug.analysisperiod as ap

def get_sun_vectors(
    epw_file, month_start, month_end, day_start, day_end, hour_start, hour_end, timestep
):
    epw_data = EPW(epw_file)

    # Create HOYs
    start_month = month_start
    start_day = day_start
    start_hour = hour_start
    end_month = month_end
    end_day = day_end
    end_hour = hour_end
    timestep = timestep

    anp = ap.AnalysisPeriod(
        start_month, start_day, start_hour, end_month, end_day, end_hour, timestep
    )

    # Initiate sunpath
    sp = Sunpath.from_location(epw_data.location)
    solar_time = False

    altitudes, azimuths, datetimes, moys, hoys, vectors, suns = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for hoy in anp.hoys:
        sun = sp.calculate_sun_from_hoy(hoy, solar_time)
        if sun.is_during_day:
            altitudes.append(sun.altitude)
            azimuths.append(sun.azimuth)
            datetimes.append(sun.datetime)
            moys.append(sun.datetime.moy)
            hoys.append(sun.datetime.hoy)
            vectors.append(sun.sun_vector)
            suns.append(sun)

    return vectors


if __name__ == "__main__":
    print("This main is plain")
