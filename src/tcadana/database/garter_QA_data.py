# This script is used to download QA sensor data from the ITk database and transform
# into a json file that works with Carleton TCAD simulation plotting scripts

import itkdb
import json
import datetime
import argparse
import time
import logging

from tcadana.serialization import to_json

logging.basicConfig(format="%(asctime)s %(levelname)4s: %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

client = itkdb.Client()
client.user.authenticate()


class QA_irrad_device:
    def __init__(self, SN):
        self.SN = SN
        self.output_jsons = {}
        self.compData = None
        self.irradData = None
        self.tests_to_process = None

        # If an error is found, error message is saved, and rest of test process is skipped
        self.error_strings = []

        # save a raw copy of the data
        self.save_raw_data = True

        # Create a map of DB entry format to the output json format
        # 	Maps out_key to 2 items: db_key and a 2nd map for values (db->out)
        key_map = {}
        key_map["TestType"] = ["testType", {"MD8_IV": "IV", "MD8_CV": "CV"}]
        key_map["DeviceType"] = ["testType", {"MD8_IV": "MD8", "MD8_CV": "MD8"}]
        key_map["Voltage"] = ["VOLTAGE", None]
        key_map["SoftwareTest"] = ["ALGORITHM", None]
        # For IV
        key_map["Current"] = ["NORM_CURRENT", None]
        key_map["Rseries"] = ["RSERIES", None]
        key_map["PowerSupply"] = ["SOURCE_METER", None]
        # For CV
        key_map["Capacitance"] = ["CAPACITANCE", None]
        # For irradiation
        key_map["Fluence"] = ["ACTUAL_FLUENCE", None]
        key_map["FluenceTarget"] = ["NOMINAL_FLUENCE", None]
        key_map["FluenceType"] = [
            "PARTICLE_AND_ENERGY",
            {
                "reactor neutrons": "neutron",
                "protons (27 MeV)": "proton_low",
                "proton (27 MeV)": "proton_low",
                "proton (23 MeV)": "proton_low",
                "protons (70 MeV)": "proton_high",
                "gamma (1.17, 1.33 MeV)": "gamma",
            },
        ]

        self.key_map = key_map

    def parse_component(self, processable_tests=None):
        """
        Parse component data and find available tests that can be processed

        * Queries component data from the database
        * Finds the IRRADIATION test data if it exists
        * Finds the available tests for this component that match the given set of processable tests

        Parameters
        ----------
        processable_tests : set of str
            set of test codes that can be processed. If None, defaults to {"MD8_IV", "MD8_CV", "MINI_CCE"}

        Returns
        -------
        None

        Attributes modified
        -------------------
        self.comp_data : dict
            component data from the database
        self.irrad_data : dict
            IRRADIATION test data if it exists
        self.tests_to_process : list
            list of available test codes that can be processed
        """
        self.compData = client.get("getComponent", json={"component": self.SN})

        if self.compData is None:
            logger.warning(f"Unable to get component for {self.SN}")
            return

        # Grab data on the IRRADIATION stage (will return None if component has no such test)
        self.irrad_data = get_testData_from_testName(self.compData, "IRRADIATION")

        # Find available tests for this component that we can process
        if processable_tests is None:
            processable_tests = {"MD8_IV", "MD8_CV", "MINI_CCE"}
        else:
            processable_tests = set(processable_tests)

        self.tests_to_process = list(
            processable_tests.intersection(
                test["code"] for test in self.compData["tests"]
            )
        )

    def process_tests(self):
        if len(self.error_strings) > 0:
            return
        for test_name in self.tests_to_process:
            testData = get_testData_from_testName(self.compData, test_name)
            if testData == None:
                error_string = "Error, component {0} test_name {1} either isn't found or has multiple ready copies. You should check what is happening for this component!".format(
                    self.SN, test_name
                )
                print(error_string, "Skipping test and continuing.")
                self.error_strings.append(error_string)
                return

            for testDatum in testData:
                this_test_json = self.translate_test_to_json(testDatum)
                if this_test_json:
                    iso_timestamp = this_test_json["Metadata"]["TimeIso"]
                    self.output_jsons[iso_timestamp] = this_test_json

                    if self.save_raw_data:
                        to_json(testDatum, f"tmp_db/{iso_timestamp}.json")

    # Translate the database information into a dictionary, and return
    def translate_test_to_json(self, testData):
        this_json_dict = {}

        # Create the metadata dictionary for the output json file
        metadata_dict = {}
        this_json_dict["Metadata"] = metadata_dict

        # Use testType to determine information Carleton json format expects
        testType_data = testData["testType"]["code"]
        metadata_dict["TestType"] = testType_data.split("_")[1]
        metadata_dict["DeviceType"] = testType_data.split("_")[0]

        # Copy information from component
        metadata_dict["Component"] = self.compData["serialNumber"]
        metadata_dict["Institute"] = testData["institution"]["code"]
        if self.compData["alternativeIdentifier"] != None:  # Not always uploaded
            metadata_dict["Batch"] = self.compData["alternativeIdentifier"].split("-")[
                0
            ]
            metadata_dict["Wafer"] = (
                self.compData["alternativeIdentifier"].split("-")[1].lstrip("W")
            )
        # TODO could get WaferType from parent, e.g. VPX37412-W00658	("WaferType": "ATLAS18R3")

        # Add general metadata
        db_datestring = testData["date"][:-5]  # Strip subseconds
        db_datestamp = datetime.datetime.fromisoformat(db_datestring)
        metadata_dict["Time"] = db_datestamp.strftime("%a, %b %d, %Y, %I:%M:%S %p")
        metadata_dict["TimeIso"] = db_datestamp.isoformat()
        metadata_dict["IsSim"] = False
        metadata_dict["XLabel"] = "Voltage"

        # Common information
        Results_list = ["Voltage"]
        Metadata_list = ["SoftwareTest"]

        # Test-specific information
        if metadata_dict["TestType"] == "IV":
            # See https://itkpd-test.unicorncollege.cz/testRunView?id=61d8a1c53be1da000aae4bc0
            Results_list += ["Current", "NORM_CURRENT_500V", "VBD"]
            Metadata_list += ["PowerSupply", "Rseries"]
        elif metadata_dict["TestType"] == "CV":
            # See https://itkpd-test.unicorncollege.cz/testRunView?id=61d8a1b23be1da000aae4b9d
            Results_list += ["Capacitance", "VFD"]
            Metadata_list += [
                "CIRCUIT_MODEL",
                "LCR_METER",
                "SIGNAL_AMPLITUDE",
                "SIGNAL_FREQUENCY",
                "SOURCE_BIAS",
            ]
        elif metadata_dict["TestType"] == "CCE":
            # See https://itkpd-test.unicorncollege.cz/testTypeView?id=5f1ec97d71645a000b7b3c47
            Results_list += [
                "CCE_500V",
                "LANDAUMPV",
                "Current",
                "HUMIDITY",
                "TEMPERATURE",
                "NORM_CURRENT",
            ]
            Metadata_list += [
                "PowerSupply",
            ]
        else:
            logger.warning(f"Cannot match test type {metadata_dict['TestType']}")

        # Find all database properties.  We will dump to output the ones not already being remapped to Carleton format
        all_database_properties = [prop["code"] for prop in testData["properties"]]
        for metadata_items in Metadata_list:
            if (
                metadata_items in self.key_map
                and self.key_map[metadata_items][0] in all_database_properties
            ):
                all_database_properties.remove(self.key_map[metadata_items][0])
        Metadata_list += all_database_properties

        # Translate database properties into Carleton metadata format
        for out_key in Metadata_list:
            self.fill_json(testData, this_json_dict, out_key, is_Metadata=True)
        for out_key in Results_list:
            self.fill_json(testData, this_json_dict, out_key, is_Metadata=False)

        # Need some hardcoding for units...
        if metadata_dict["TestType"] == "IV":
            this_json_dict["Metadata"]["VoltageUnit"] = "V"
            this_json_dict["Metadata"]["CurrentUnit"] = "A/cm2"
        elif metadata_dict["TestType"] == "CV":
            this_json_dict["Metadata"]["VoltageUnit"] = "V"
            this_json_dict["Metadata"]["CapacitanceUnit"] = "pF/cm2"
        # 			"CapacitanceUnit": "pF", "ResistanceUnit": "kOhm"

        # Fill in irradiation information if applicable, and check for database issues
        testedAtStage = testData["components"][0]["testedAtStage"]["code"]
        if testedAtStage == "PRE-IRRAD_TESTS":
            this_json_dict["Metadata"]["Fluence"] = 0
            this_json_dict["Metadata"]["FluenceTarget"] = 0
            this_json_dict["Metadata"]["FluenceType"] = "None"
        elif testedAtStage == "POST-IRRAD_TESTS":
            if self.irradData != None:
                all_irrad_properties = [
                    prop["code"]
                    for prop in self.irradData["properties"] + self.irradData["results"]
                ]
                irrad_Metadata_list = [
                    "Fluence",
                    "FluenceTarget",
                    "FluenceType",
                ] + all_irrad_properties
                # Translate database properties into Carleton metadata format
                for out_key in irrad_Metadata_list:
                    self.fill_json(
                        self.irradData, this_json_dict, out_key, is_Metadata=True
                    )
            else:
                error_string = "Error, component {0} test {1} is marked as POST-IRRAD_TESTS but doesn't have any IRRADIATION data.".format(
                    self.SN, testType_data
                )
                print(error_string, "Skipping test and continuing.")
                self.error_strings.append(error_string)
                return None
        else:
            error_string = "Error,  component {0} test {1} doesn't have an understandable testedAtStage {2}.".format(
                self.SN, testType_data, testedAtStage
            )
            print(error_string, "Skipping test and continuing.")
            self.error_strings.append(error_string)
            return None

        # Reorder metadata items for file readability
        reordered_metadata_dict = {}
        prefered_order = [
            "TestType",
            "DeviceType",
            "IsSim",
            "WaferType",
            "Fluence",
            "FluenceTarget",
            "MeasurementType",
            "TimeIso",
        ]
        for label in prefered_order:
            if label in this_json_dict["Metadata"]:
                reordered_metadata_dict[label] = this_json_dict["Metadata"][label]
        reordered_metadata_dict.update(
            this_json_dict["Metadata"]
        )  # Add all other entries in whatever order
        this_json_dict["Metadata"] = reordered_metadata_dict

        return this_json_dict

    # Function to fill json from DB info according to provided definitions
    def fill_json(self, test, this_json_dict, out_key, is_Metadata):
        # If the key is in the key_map, find db_info
        if out_key in self.key_map:
            db_key, data_map = self.key_map[out_key]
        else:  # database and output keys are the same
            db_key = out_key
            data_map = None

        db_data = get_data_from_test(test, db_key, access_type="value")

        # If the database data needs to be remapped for Carleton format
        if data_map == None:
            out_data = db_data
        else:
            out_data = data_map[db_data]

        if out_key == "Fluence" or out_key == "FluenceTarget":
            out_data = "{:.2e}".format(out_data)

        # Save as a result or as Metadata
        if is_Metadata:
            this_json_dict["Metadata"][out_key] = out_data
        else:
            this_json_dict[out_key] = out_data

        return


# Get a database item (default is value) for a specific parameter from the test object
def get_data_from_test(test, param_name, access_type="value"):
    this_data = [
        this_result[access_type]
        for this_result in test["properties"] + test["results"]
        if this_result["code"] == param_name
    ]
    if len(this_data) == 1:
        return this_data[0]
    elif len(this_data) == 0:
        print("Error, could not find {0} in test {1}".format(param_name, test))
        exit(1)
    elif len(this_data) >= 2:
        print(
            "Error, found multiple instances of {0} in test {1}".format(
                param_name, test
            )
        )
        exit(1)


# Get test's data using ID.  ID retrieved from a matching test_name code in testRuns in tests in the component
# Return None if the test_name doesn't exist, or if there are multiple versions of the test
def get_testData_from_testName(component, test_name):
    test_ids = (
        test_run["id"]
        for test in component["tests"]
        if test["code"] == test_name
        for test_run in test["testRuns"]
    )

    # For each ID returned, grab the data and check that it is ready (sometimes data is deleted, leading to multiple copies)
    ready_tests = []  # could change to generator
    for test_id in test_ids:
        test_data = client.get("getTestRun", json={"testRun": test_id})
        if test_data["state"] == "ready":
            ready_tests.append(test_data)

    if test_name == "IRRADIATION" and len(ready_tests) == 2:
        return ready_tests[0]
        # TODO these are interesting tests with both gamma and neutron irradiation!  They also have both Pre-irrad and Post-irrad tests!
        return None
    if len(ready_tests) > 1:
        logger.warning("multiple tests were found")

    return ready_tests


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="%prog [options]",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--outFile",
        dest="outFile",
        default="ITkStrip_QA_data.json",
        help="Output json file name for test dictionary",
    )
    parser.add_argument(
        "--nTests",
        dest="nTests",
        default=-1,
        type=int,
        help="Number of tests to process, -1 for all. ",
    )
    args = parser.parse_args()

    output_dict = {}

    # Gather all SENSOR_MINI_MD8 and SENSOR_TESTCHIP_MD8 components
    # Each SENSOR_MINI_MD8 is either a Mini or MD8, and each SENSOR_TESTCHIP_MD8 is either a Testchip or MD8
    # https://itkpd-test.unicorncollege.cz/componentManagerGate/componentTypeDetail?id=5e94981e5fbf4f000a5c27eb
    # The pre-rad CCE data are uder SENSOR_QAMINI_TEST (Sensor QAmini test)
    component_type_format = {
        "componentType": [
            "SENSOR_MINI_MD8",
            # "SENSOR_TESTCHIP_MD8",
            # "SENSOR_QAMINI_TEST",
        ],
        # "currentStage": ["PASS", "PASS", "PRE-IRRAD_TESTS"],
        # "componentType": ["SENSOR_QAMINI_TEST"],
        # "currentStage": ["PRE-IRRAD_TESTS"],
        "currentStage": ["PASS"],
        "pageInfo": {"pageSize": 50},
    }
    all_components = client.get("listComponents", json=component_type_format)
    logger.info(f"Found {all_components.total} test samples.")

    if args.nTests == -1:
        args.nTests = all_components.total

    start_time = time.time()
    test_errors = []
    nProcessed = 0
    for this_comp in all_components:
        if nProcessed >= args.nTests:
            break
        sn = this_comp["serialNumber"]
        # For testing: sn = "20USBSL0100658"
        # problem 20USBSX0100400
        logger.info(f"Processing {sn}")
        this_device = QA_irrad_device(sn)
        this_device.parse_component(["MINI_CCE", "MD8_IV"])
        this_device.process_tests()

        if len(this_device.error_strings) > 0:
            test_errors += this_device.error_strings
        else:
            output_dict.update(this_device.output_jsons)

        nProcessed += 1
        if nProcessed % 50 == 0:
            logger.info(f"Processed {nProcessed} tests so far")

    end_time = time.time()
    logger.info(
        f"It took {time.time()-start_time} seconds to process {nProcessed} tests"
    )

    if test_errors:
        logger.info(f"{len(test_errors)}/{nProcessed} tests were failed.")
        for err in test_errors:
            print(err)

    # Save data to output json file
    to_json(output_dict, args.outFile)
