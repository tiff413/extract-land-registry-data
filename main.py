import json
import logging

"""
This is a initial, prototype of a solution to parse the schedule of notices of lease API.
For the scope of this exercise, I am reading a single input json file (schedule_of_notices_of_lease_examples.json) and 
writing a new json to an output file (output.json). 

This python script achieves:
    * Cleaning of over 90% of schedule data to a dictionary of indexed columns
      e.g. FROM:
        "entryText": [
            "09.07.2009      Endeavour House, 47 Cuba      06.07.2009      EGL557357  ",
            "Edged and       Street, London                125 years from             ",
            "numbered 2 in                                 1.1.2009                   ",
            "blue (part of)"
        ]
      TO:
        "entryText": {
            "0": "09.07.2009 Edged and numbered 2 in blue (part of)",
            "1": "Endeavour House, 47 Cuba Street, London",
            "2": "06.07.2009 125 years from 1.1.2009",
            "3": "EGL557357"
        }
    * Schedule entries that were not able to be resolved into this format have just been left blank
    
The process is as follows:
    * Parse every schedule entry
    * For each line in entryText, 
        * If length of line == 73, segment the line into its columns using expected indices
        * If length of line != 73, check if line matches the edge cases or cases identified where the missing columns 
          or position of columns are known
        * If it is a case where the column cannot be resolved, log with a message and continue
    * If all lines are resolved to columns, update the json. Else remove entryText
    
To improve on this solution beyond the scope of this exercise:
    * Improve logging and process to manually resolve/clean schedule entries when necessary
    * When necessary, involve previously resolved and indexed lines in the resolution of new lines of the same schedule
      entry
    * Following on above, use semantics of previously resolved and indexed lines to aid in resolving new lines. There 
      are a handful of identifiable semantic patterns w.r.t. matching a phrase to an unfinished sentence, e.g. dates 
      "28.11.2014" connected to unfinished phrases like "5 years from", closing brackets like "third floors)". These 
      phrases could be matched to the right columns using NLP or intelligence tools
    * I think the ultimate solution looks like a proprietary AI tool for this data source, that learns from previous 
      schedule entries to resolve, index and clean data, as well as identify failed resolutions for manual resolution
    * Another solution, could be to use scanning/imaging ML technology to analyse the pdf and the visual position of 
      the columns to better understand where data should be indexed
    
"""


def get_json_from_file(file_path):
    with open(file_path, "r") as file:
        return json.load(file)


# Hard coded static variables for this exercise. Depending on use case, could be configurable and inputted in fn params
COLUMN_INDICES = [0, 16, 46, 62, 73]
# Commonly found 1st column lines
FIST_COLUMN_SIGNATURES = ["blue (part of)", "plan 1", "plan", "of", ")", "blue", "of)"]


def split_string_into_segments(s):
    # Use global variables for ease, cleanliness of this exercise. Ideally, inputted or handled in a way that doesn't
    # require initiating every time fn is called
    global COLUMN_INDICES, FIST_COLUMN_SIGNATURES

    string_segments = []

    # EDGE CASE: 2 instances of missing space at start of string
    # e.g. "Edged and                                    99 years                   "
    if len(s) == 72:
        store_s = s
        s = " " + store_s
    # EDGE CASE: 1 instance of fraction taking 2 extra chars
    # e.g. "9                                             74 1/4 years from             "
    # TODO: this is a hack fix! Ideally need to check all lines for fractions, not just those larger than 73
    elif len(s) > 73:
        s = s[:-3]

    # CASE: all columns available (73% of all lines). Segment strings into 4 columns
    if len(s) == 73 or s in FIST_COLUMN_SIGNATURES:
        for n in range(len(COLUMN_INDICES)-1):
            if len(s) <= COLUMN_INDICES[n+1]:
                string_segments.append(s[COLUMN_INDICES[n]:])
                break
            else:
                string_segments.append(s[COLUMN_INDICES[n]:COLUMN_INDICES[n+1]])

    # Shorter lines contain cases where some columns are unavailable
    else:
        s_stripped = s.strip()
        if s.endswith("                           "):
            # CASE: missing 1st column (<1% of lines)
            string_segments = ["", s_stripped]
        elif s.endswith("          "):
            # CASE: contains 3rd column only (15% of lines)
            if len(s_stripped) < 30:
                string_segments = ["", "", s_stripped]
            # CASE: contains 2nd and 3rd column (3.8% of lines)
            else:
                string_segments = ["", s_stripped]
        else:
            # TODO: For these cases (9.7% of lines), manual resolution may be required or the use of other technologies
            # possibly NLP or intelligence to validate the semantics of the complete columns
            if len(s) > 46:
                # contains either columns 1-3 or 2-4
                raise Exception("Cannot handle this case yet. Contains either columns 1-3 or 2-4")
            else:
                # Contains any single column, or some unaccounted for combinations of columns
                # Some semantic patterns can be seen here. Often, these lines are dates e.g. "28.11.2014", which can be
                # connected to unfinished phrases in a column e.g. "5 years from". Another pattern/clue is closing
                # brackets e.g. "third floors)".
                raise Exception("Cannot handle this case yet")

    return string_segments


def parse_json(root):
    for schedule_entry in root:
        schedule_entries = schedule_entry["leaseschedule"]["scheduleEntry"]
        for entry in schedule_entries:
            entry_text = entry["entryText"]

            # Store cleaned, organised data indices here
            parsed_entry_text = {}

            is_note = False
            is_failed_parse = False

            for line in entry_text:
                # Skip line if empty
                if line is None:
                    continue

                # For cancelled records, put line on first index. No need to segment line into columns
                if "CANCELLED on" in line:
                    parsed_entry_text[0] = line
                    continue

                starts_with_note = line.startswith("NOTE")
                if not starts_with_note and not is_note:
                    try:
                        # Split line into segments denoting the columns, then add each segment to respective index
                        line_segments = split_string_into_segments(line)
                        # Make sure there are not more than 4 columns
                        assert len(line_segments) <= 4, "Invalid number of columns"
                        for i, line_segment in enumerate(line_segments):
                            if line_segment.isspace():
                                continue
                            line_segment_stripped = line_segment.strip()
                            if i in parsed_entry_text:
                                parsed_entry_text[i] += " " + line_segment_stripped
                            else:
                                parsed_entry_text[i] = line_segment_stripped
                    # Mark as a failed parse
                    except Exception as e:
                        is_failed_parse = True
                        logging.error("Failed to parse line: {}. {}".format(line, e))
                        continue
                elif starts_with_note:
                    # for new note, add new index
                    is_note = True

                    keys = parsed_entry_text.keys()
                    if keys:
                        index = max(keys) + 1
                    else:
                        index = 0
                    parsed_entry_text[index] = line.strip()
                else:
                    # for existing note, append to largest index
                    max_index = max(parsed_entry_text.keys())
                    parsed_entry_text[max_index] += " " + line.strip()

            # Update json if all lines are parsed
            if not is_failed_parse:
                entry["entryText"] = parsed_entry_text
            # If failed to parse all lines, remove entryText and leave as empty
            # TODO: Ideally these records should be separated and manually resolved
            else:
                entry["entryText"] = {}

    return root_json


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # ### EXECUTE SCRIPT ###
    logging.info('*****Starting*****')
    path = "schedule_of_notices_of_lease_examples.json"

    # Input json file
    root_json = get_json_from_file(path)
    # Parse json. This fn can also be called if the source was an API
    parsed_json = parse_json(root_json)
    logging.info("Finished parsing json")

    # Write new json into output file
    output_file_name = "output.json"
    logging.info("Writing resulting json to: {}".format(output_file_name))
    with open(output_file_name, "w") as outfile:
        outfile.write(json.dumps(parsed_json, indent=4))

    logging.info("*****Completed*****")
