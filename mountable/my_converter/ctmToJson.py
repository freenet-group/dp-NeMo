import json
from pathlib import Path
from optparse import OptionParser
import re
import os
import re
from tqdm.auto import tqdm



parser = OptionParser()
parser.add_option("-m", "--manifest", dest = "manifest", help="Alternative to --timestamps. The nemo manifest used to create the timestamps.", default = None)
parser.add_option("-o", "--outputDefault", dest = "outputDefault", help = "path for the output default, if no archfolder field is provided in the manifest")


(options, args) = parser.parse_args()

manifestPath = options.manifest
outputPathDefault = options.outputDefault

def is_entry_in_all_lines(manifest_filepath, entry):
    """
    Returns True is entry is a key in all of the JSON lines in manifest_filepath.
    """
    with open(manifest_filepath, 'r') as f:
        for line in f:
            data = json.loads(line)

            if entry not in data:
                return False

    return True


if manifestPath is not None:
        manifestLines = Path(manifestPath).read_text().split("\n")
        if not is_entry_in_all_lines(manifestPath, "audio_filepath"):
            raise RuntimeError(
            "At least one line in manifest does not contain an 'audio_filepath' entry. "
            "All lines should contain an 'audio_filepath' entry."
            )
        
        if not is_entry_in_all_lines(manifestPath, "text"):
            raise RuntimeError(
            "At least one line in manifest does not contain an 'text' entry. "
            "All lines should contain an 'text' entry."
            )
        
        if not is_entry_in_all_lines(manifestPath, "word_level_ctm_filepath"):
            raise RuntimeError(
                "At least one line in manifest does not contain an 'word_level_ctm_filepath' entry. "
                "All lines should contain an 'word_level_ctm_filepath' entry."
                "You might have provided a manifest from before the align process."
            )
else:
    raise RuntimeError(
            "Please provide the manifest generated by the align process."
            "Use -m or --manifest"
        )

if outputPathDefault is None:
    if not is_entry_in_all_lines(manifestPath, "archfolder"):
            raise RuntimeError(
                "At least one line in manifest does not contain an 'archfolder' entry."
                "But you did not provide a --outputDefault."
                "Please add archfolder to all manifest lines, or give a outputDefault."
            )
    else:
        print("You did not provide a outputDefault, but all manifest lines have an archfolder.")
        print("We will put each report in the corresponding archfolder.")

usedOverwrites = set()
neverUsedDefaultFolder = True
with open(manifestPath, 'r') as manifest_file:
        for manifest_idx, manifest_line in enumerate(tqdm(manifest_file, desc=f"Reading Manifest {manifestPath} ...", ncols=120)):
            data = json.loads(manifest_line)
            word_level_ctm_file_path = data['word_level_ctm_filepath']
            full_text = data['text']
            solutions = []
            ctm_file = open(word_level_ctm_file_path, 'r')
            lines = ctm_file.readlines()
            for line in lines:
                segments = line.split()
                audio_generated_id = segments[0]
                second_value = segments[1]
                start_ts = segments[2]
                duration = segments[3]
                end_ts = round(float(start_ts)+float(duration), 2) # we do not get more precision than two digits from NeMo
                word = segments[4]
                solution = {'word': word,
                    'start_time': start_ts,
                    'end_time': end_ts,
                    'confidence': 1} # nvidia nemo doesn't give confidence, so we use a dummy value
                solution['word'] = word
                solutions.append(solution)
                
            ibm_ts_list = []
            for solution in solutions:
                word = solution['word']
                start = solution['start_time']        
                end = solution['end_time']
                package = [word,start,end]
                ibm_ts_list.append(package)     

            ibm_conf_list = []
            for solution in solutions:
                word = solution['word']
                confidence = solution['confidence']
                package = [word,confidence]
                ibm_conf_list.append(package)   

            outputDictionary = [{
                    "result_index" : 0,
                    "results":
                    {
                            "final": [True],
                            "alternatives": [{
                                    "transcript": full_text,
                                    "confidence": 1,
                                    "timestamps": ibm_ts_list,
                                    "word_confidence": ibm_conf_list
                            }],
                            "word_alternatives": [] # we do not provide alternatives, this is just for compatiblity with ibm
                    }
            }]
            
            outputFileForThis = os.path.basename(word_level_ctm_file_path)
            outputPathForThis = outputPathDefault
            if 'archfolder' in data:
                outputPathForThis = data['archfolder'] # if we find a given archfolder in the manifest, we overwrite the given default folder
                # this allows us to mix different archfolders in the same manifest
                usedOverwrites.add(data['archfolder'])
            else:
                neverUsedDefaultFolder = False
            fullOutputPathForThis = os.path.join(outputPathForThis, outputFileForThis)

            with open(fullOutputPathForThis, "w") as outfile:
                    json.dump(outputDictionary, outfile)

if len(usedOverwrites) == 0:
    print("Done! We did not find 'archfolder' in the manifest lines, so we put all results in the provided default folder " + outputPathDefault + ". ")
elif neverUsedDefaultFolder:
    print("Done! Check results in the manifest-provided archfolders: " + str(usedOverwrites) + ". We did not need the default folder.")
else:
    print("Done! Check results both in the manifest-provided archfolders: " + str(usedOverwrites) + " and the default " + outputPathDefault)
