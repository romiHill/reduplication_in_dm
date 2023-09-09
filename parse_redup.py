"""
Automatically parse patterns in reduplication, via a Distributed Morphology Framework
Important: 
--- Phrases cannot contain newline characters (only with features and phonological content, where that content may be null)
--- Morphemes must be unique (or have unique names)
--- vi_rules.txt file must have all nodes grouped together (i.e. all "T" morphemes in one section, etc)

"""
# ------------------------------------------------------------------------ #
# ------------ LIBRARIES ------------ #
# ------------------------------------------------------------------------ # 
import os, sys, glob
import re, copy, collections, itertools
import svgling
from argparse import ArgumentParser

# ------------------------------------------------------------------------ #
# ------------ CONSTANTS ------------ #
# ------------------------------------------------------------------------ #
LENGTH_OF_SINGLE_ELEMENT_LIST = 1
LENGTH_OF_DOUBLE_ELEMNT_LIST = 2

SECOND_LAST_INDEX = -2
LAST_INDEX = -1

INITIAL_INDEX = 0
SECOND_INDEX = 1
THIRD_INDEX = 2

NODE_INDEX = 0
PHONOLOGICAL_MATERIAL_INDEX = -1

VOWEL_LST = ['a', 'e', 'i', 'o', 'u']

# ------------------------------------------------------------------------ #
# ------------ CLASSES ------------ #
# ------------------------------------------------------------------------ #
class IndexToReplace:
    def __init__(self, initial, final):
        self.initial = initial
        self.final = final
    def __str__(self):
        return f'initial: {self.initial}\tfinal: {self.final}'

# ------------------------------------------------------------------------ #
# ------------ HELPER FUNCTIONS ------------ #
# ------------------------------------------------------------------------ #

def parse_arguments():
    """
    Parse arguments from user input
    """
    parser = ArgumentParser(description = __doc__)
    parser.add_argument('-i', '--inputFolder', type = str, help = 'Folder containing files to parse. The folder containing linguistic information must have the same name, in the same location as the script.')
    parser.add_argument('-o', '--outputFolder', type = str, help = 'Folder to save the output svg files')
    args = parser.parse_args()

    if not os.path.exists(args.inputFolder):
        parser.print_help()
        print(f'Input folder does not exist, or was not specified correctly')
        sys.exit(0)

    if not os.path.exists(args.outputFolder):
        os.makedirs(args.outputFolder)
        print(f'Output folder {args.outputFolder} was created')

    else:
        prev_output_files_path = f'{args.outputFolder}/*'
        prev_output_files = glob.glob(prev_output_files_path)
        for f in prev_output_files:
            os.remove(f)

    return args

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- SMALLER HELPERS --- #
# ---------------------------- #

def flatten(lst):
    """
    Return a flattened list from an (arbitrarily) embedded list of lists
    """
    if isinstance(lst, collections.abc.Iterable) and not isinstance(lst, str):
        return [a for i in lst for a in flatten(i)]
    else:
        return [lst]

# ------------------------------------------------------------------------ #

def list_to_tuple(in_lst):
    """
    Convert an embedded list into an embedded tuple
    https://stackoverflow.com/questions/1014352/how-do-i-convert-a-nested-tuple-of-tuples-and-lists-to-lists-of-lists-in-python
    """
    return tuple(map(list_to_tuple, in_lst)) if isinstance(in_lst, (tuple, list)) else in_lst


# ------------------------------------------------------------------------ #

def is_vowel_initial(root):
    if root[PHONOLOGICAL_MATERIAL_INDEX][INITIAL_INDEX] in VOWEL_LST:
        return True
    return False

# ------------------------------------------------------------------------ #

def find_embedded_index(input_list, elem):
    """
    Find the index of an element in an embedded list using depth first search
    """
    for i in range(len(input_list)):
        if isinstance(input_list[i], list):
            # if current element is a list, call the function again
            result = find_embedded_index(input_list[i], elem)
            # return the result (index of elem within its index) and i (the index of current list)
            if result:
                return [i] + result
        # return the index when the element is found
        elif input_list[i] == elem:
            return [i]
    # if the element doesn't exist return false
    print(f'{elem} doesn\'t exist in {input_list}, please fix')
    sys.exit(1)

# ------------------------------------------------------------------------ #

def find_deepest_depth(data):
    if isinstance(data, list):
        depths = [find_deepest_depth(item) for item in data]
        return max(depths) + 1 if depths else 1
    else:
        return 0

# ------------------------------------------------------------------------ #

def generate_permutations(nested_list_of_lists):
    permutations = list(itertools.product(*nested_list_of_lists))

    for i, perm in enumerate(permutations):
        permutations[i] = list(perm)

    return permutations

# ------------------------------------------------------------------------ #

def flatten_list_of_dicts(list_of_dicts):
    flat_dict = {}
    for dct in list_of_dicts:
        flat_dict.update(dct)
    return flat_dict

# ------------------------------------------------------------------------ #

def find_all_indices(word, environment):
    """
    Find all occurrences of an environment within the word
    """
    indices = []
    index = 0
    while True:
        index = word.find(environment, index)
        if index == -1:
            break
        indices.append(index)
        index += 1
    return indices

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- ADD RULES AT BINARY TREES --- #
# ---------------------------- #

def add_leaf_at_rule(inner, embedded_index, leaf, rule):
    """
    Unpack rule at given index
    Rule is unary
    """
    # end of list requires different slicing
    if embedded_index[SECOND_LAST_INDEX] == len(inner) - 1:
        inner[embedded_index[SECOND_LAST_INDEX]:] = [[rule, leaf[INITIAL_INDEX]]]
    else:
        inner[embedded_index[SECOND_LAST_INDEX]:LAST_INDEX] = [[rule, leaf[INITIAL_INDEX]]]

    return inner 

# ------------------------------------------------------------------------ #

def add_branches_at_rule(inner, embedded_index, branches, rule):
    """
    Unpack rule at given index
    Rule is binary
    """
    # end of list requires different slicing
    if embedded_index[SECOND_LAST_INDEX] == len(inner) - 1:
        inner[embedded_index[SECOND_LAST_INDEX]:] = [[rule, branches[INITIAL_INDEX], branches[SECOND_INDEX]]]
    else:
        inner[embedded_index[SECOND_LAST_INDEX]:LAST_INDEX] = [[rule, branches[INITIAL_INDEX], branches[SECOND_INDEX]]]
    return inner 

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- PROCESS STRUCTURE --- #
# ---------------------------- #

def unprocessed_psr_in_structure(lst):
    """
    Checks whether there is an element that is a list of length one
    """
    # initial structure has length 1, and has not been processed before
    if len(lst) == LENGTH_OF_SINGLE_ELEMENT_LIST:
        return True
    else:
        for element in lst:
            if isinstance(element, list):
                if len(element) == LENGTH_OF_SINGLE_ELEMENT_LIST:
                    return True
                # element is a list of length > 1, check elements inside the list
                elif unprocessed_psr_in_structure(element):
                    return True
        # end of all embedded lists and never found a list of length one
        return False

# ------------------------------------------------------------------------ #

def is_rule_list(inner, embedded_index):
    """
    Helper function to extract the element that has been identified as a potential rule to unpack
    Returns a boolean if the element is a list
    """
    if len(embedded_index) == LENGTH_OF_SINGLE_ELEMENT_LIST:
        return type(inner[INITIAL_INDEX]) == list
    else:
        return type(inner[embedded_index[SECOND_LAST_INDEX]]) == list

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- CREATE STRUCTURE --- #
# ---------------------------- #

def create_base_structure(base_struc, all_psr):
    """
    Create underlying verb structure based off custom file
    Assumes there is only one structure
    """

    # while loop ensures all rules are expanded, regardless of all_psr order
    while unprocessed_psr_in_structure(base_struc):
        for rule in all_psr:
            if rule in flatten(base_struc):
                # index of rule in embedded list
                embedded_index = find_embedded_index(base_struc, rule)
                # top node has only one element, process is slightly different
                if len(base_struc) == LENGTH_OF_SINGLE_ELEMENT_LIST:
                    base_struc += all_psr[rule]

                # replace other nodes with their elements
                else:
                    inner = base_struc
                    # iterate up to second-last embedded_index
                    for i in embedded_index[:SECOND_LAST_INDEX]:
                        inner = inner[i]

                    # update only if the next element is a string, not a list (has not been processed before)
                    if is_rule_list(inner, embedded_index):
                        # rule is unary branching
                        if len(all_psr[rule]) == LENGTH_OF_SINGLE_ELEMENT_LIST:
                            inner = add_leaf_at_rule(inner, embedded_index, all_psr[rule], rule)

                        # rule is binary branching
                        elif len(all_psr[rule]) == LENGTH_OF_DOUBLE_ELEMNT_LIST:
                            inner = add_branches_at_rule(inner, embedded_index, all_psr[rule], rule)


    return base_struc

# ------------------------------------------------------------------------ #

def reduplicate_base_structure(base_struc, dominated_nodes, root):
    """
    Create reduplicated structure from base
    For now, only check whether root is vowel initial
    Data from other languages may require this step to be extended, but this will suffice for now.
    """
    all_redup_struc = []
    for target_node_and_environment in dominated_nodes:
        node = target_node_and_environment[INITIAL_INDEX]
        environment = target_node_and_environment[SECOND_INDEX]

        if reduplicate_environments(environment, root):
            embedded_index = find_embedded_index(base_struc, node)

            redup_struc = copy.deepcopy(base_struc)
            inner = redup_struc
            # iterate up to second-last embedded_index
            for i in embedded_index[:SECOND_LAST_INDEX]:
                inner = inner[i]

            # insert REDP above node to be dominated
            inner[embedded_index[SECOND_LAST_INDEX]] = ['REDP', 'RED', inner[embedded_index[SECOND_LAST_INDEX]]]
            all_redup_struc.append(redup_struc)
    return all_redup_struc

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- REDUPLICATION PROCESSES --- #
# ---------------------------- #

def reduplicate_environments(environment, root):
    """
    Return True if redP should dominate a node
    """
    # empty environment means reduplication is allowed in any condition
    if not environment:
        return True
    # environment requires root to be vowel initial
    elif ( environment == "VOWEL" ) and ( root[INITIAL_INDEX] in VOWEL_LST):
        return True
    return False

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- VOCABULARY INSERTION --- #
# ---------------------------- #

def mark_depth_for_vi(data, vi_rules, depth):
    """ 
    Insert same of *s at each depth of the tree
    To mark where Vocabulary Items are inserted
    In preparation for VI from bottom up
    """
    # Check if the element is a list
    if isinstance(data, list):
        result = []
        for item in data:
            result.append(mark_depth_for_vi(item, vi_rules, depth - 1))
        return result

    elif isinstance(data, str):
        if data in vi_rules or data == "RED":
            return data + '*' * (depth)
        else:
            return  data
    else:
        return data

# ------------------------------------------------------------------------ #

def replace_stars_with_vi(data, current_depth, vi_rules):
    """
    Replace * characters with vocabulary insertion, to apply VI from bottom up
    """
    if isinstance(data, list):
        return [replace_stars_with_vi(item, current_depth, vi_rules) for item in data]
    elif isinstance(data, str):
        if data.count("*") == current_depth:
            rule = vi_rules[data.strip("*")]
            out_rule = "\n".join(rule)
            if out_rule[INITIAL_INDEX] != '\n':
                out_rule = '\n' + out_rule
            return data.strip('*') + out_rule

    return data

# ------------------------------------------------------------------------ #

def depth_at_red(data, current_depth):
    """ 
    Returns True if current node is RED at current depth
    """
    if isinstance(data, list):
        if ('RED' + ("*" * current_depth)) in data:
            return True
        for item in data:
            if depth_at_red(item, current_depth):
                return True
    return False

# ------------------------------------------------------------------------ #

def remove_stars_from_structure(data):
    """
    Remove * characters, for pretty printing
    """
    if isinstance(data, list):
        return [remove_stars_from_structure(item) for item in data]
    elif isinstance(data, str):
        return data.strip('*')
    else:
        return data

# ------------------------------------------------------------------------ #

def add_vi_rule_redup(data, vi_rules, scope, epenthesis, environment):
    """
    Add RED VI rule based on previously spelt out morphemes
    Phonological content is identified as being the final string that follows a new line
    """
    phonological_content = ''
    first_node_to_copy = True
    template_filled = False
    for item in data:
        # new line character means phonological output has been added to the structure
        if '\n' in item:
            item = item.split('\n')
            if first_node_to_copy:
                node = item[NODE_INDEX]
                vowel_initial = is_vowel_initial(item)
                first_node_to_copy = False

            if scope == 'bisyllabic':
                vowel_count = 0

                for char in item[PHONOLOGICAL_MATERIAL_INDEX]:
                    if not template_filled:
                        phonological_content += char
                        if char in VOWEL_LST:
                            vowel_count += 1
                        if vowel_count >= 2:
                            template_filled = True
                    else:
                        break

            else:
                phonological_content += item[PHONOLOGICAL_MATERIAL_INDEX]
        if template_filled:
            break


    if epenthesis:
        if environment == "VOWEL":
            if vowel_initial and node == 'V':
                phonological_content += epenthesis
        else:
            phonological_content += epenthesis
    vi_rules['RED'] = ['', phonological_content]

    return vi_rules

# ------------------------------------------------------------------------ #

def apply_vi_rules(syntactic_data, vi_rules, phonological_rules, scope, epenthesis, environment):
    """
    Insert Vocabulary Items progressively
    """
    depth = find_deepest_depth(syntactic_data) + 1
    marked_syntactic_data = mark_depth_for_vi(syntactic_data, vi_rules, depth)
    all_data_vi_lst = []
    for i in range(1, depth):
        if depth_at_red(marked_syntactic_data, i):
            vi_rules = add_vi_rule_redup(flatten(marked_syntactic_data), vi_rules, scope, epenthesis, environment)

        marked_syntactic_data = replace_stars_with_vi(marked_syntactic_data, i, vi_rules)
        all_data_vi_lst.append(marked_syntactic_data)

    phonological_word = get_phonological_word(all_data_vi_lst[LAST_INDEX], expand = False)

    # ensure that all phonological processes have been applied
    while any(environment in phonological_word for environment in phonological_rules):
        all_data_vi_lst[LAST_INDEX] = apply_phonological_processes(all_data_vi_lst[LAST_INDEX], phonological_rules)
        phonological_word = get_phonological_word(all_data_vi_lst[LAST_INDEX], expand = False)

    all_data_vi_lst.append(all_data_vi_lst[LAST_INDEX])

    return all_data_vi_lst

# ------------------------------------------------------------------------ #

def get_phonological_word(final_vi_data, expand):
    """ 
    Return the flat phonological word 
    """
    morphemes = {}
    for item in flatten(final_vi_data):
        if '\n' in item:
            item = item.split('\n')
            phonological_content = item[LAST_INDEX]
            morpheme_node = item[INITIAL_INDEX]
            morphemes[morpheme_node] = phonological_content
    if expand:
        return phonological_content, morpheme_node, morphemes, ''.join(morphemes.values())
    return ''.join(morphemes.values())

# ------------------------------------------------------------------------ #

def find_and_replace_element(data, target, replacement, is_separate_node: bool, is_initial_node: bool, index_to_replace):
    """
    Replace the phonological string based on general language specific phonological requirements
    """
    if isinstance(data, list):
        for i, item in enumerate(data):
            data[i] = find_and_replace_element(item, target, replacement, is_separate_node, is_initial_node, index_to_replace)
    else:
        data_lst = data.split('\n')
        data_to_match = [data_lst[INITIAL_INDEX]] + [data_lst[LAST_INDEX]]
        target_to_match = target.split('\n')

        if data_to_match == target_to_match:
            data = data.split('\n')
            node = data[INITIAL_INDEX]
            additional_material = data[INITIAL_INDEX + 1:LAST_INDEX]
            phon_string = list(data[LAST_INDEX])
            replace_phon_string = replacement.split('\n')[LAST_INDEX]
            # print(f'\tdata: {data}')

            # same node mean replacement within list

            # separate nodes require replacement at boundaries
            if is_separate_node:
                # if we are replacing the first node, replace the last character
                if is_initial_node:
                    phon_string[LAST_INDEX] = replace_phon_string
                # if we are replacing the second node, replace the first character
                else:
                    phon_string[INITIAL_INDEX: len(replace_phon_string)] = replace_phon_string

                phon_string = "".join(phon_string)
            # for now, only deal with phonological processes at the start of morpheme
            else:
                # print(f'--- same morpheme ---')
                # replace the first character
                if is_initial_node:
                    # print(f'\tbefore (initial node to change): {phon_string}')
                    phon_string[index_to_replace.initial] = replace_phon_string
                    # print(f'\tafter (initial phoneme to change): {phon_string}')
                # replace the second character
                else:
                    # print(f'\tbefore (final node to change): {phon_string}')
                    phon_string[index_to_replace.final] = replace_phon_string
                    # print(f'\tafter (final phoneme to change): {phon_string}')
                    
                phon_string = "".join(phon_string)

            additional_material = "\n".join(additional_material)

            if additional_material:
                data = f'{node}\n{additional_material}\n{phon_string}'
            # avoid double newline characters
            else:
                data = f'{node}\n{phon_string}'

    return data

# ------------------------------------------------------------------------ #


# ---------------------------- #
# --- GENERAL PROCESSES --- #
# ---------------------------- #

def apply_phonological_processes(final_vi_data, phonological_rules):
    out_lst = copy.deepcopy(final_vi_data)
    morphemes = {}

    # separate words by morphemes
    # key is (abstract) morpheme, value is phonological string
    phonological_content, morpheme_node, morphemes, phonological_word = get_phonological_word(final_vi_data, expand = True)

    for environment, rule in phonological_rules.items():
        # include this if statement to improve efficiency
        if environment in phonological_word:
            # find location where the rule is applied
            indices = find_all_indices(phonological_word, environment)
            # keep track of index location in flat string
            count = 0
            # find the node where the phonological process is applied
            for node, phon_string in morphemes.items():
                for i, char in enumerate(phon_string):
                    if count in indices:
                        first_changed_phoneme = rule[INITIAL_INDEX]
                        second_changed_phoneme = rule[SECOND_INDEX]
                        target = f'{node}\n{phon_string}'
                        replacement = f'{node}\n{first_changed_phoneme}'

                        pretty_target = target.split('\n')
                        pretty_replacement = replacement.split('\n') + [second_changed_phoneme]
                        # print(f'Target: {pretty_target}\tReplacement: {pretty_replacement}')
                        is_initial_node = True
                        # if char is last character in string, then phonological process applies at morpheme boundary
                        if i == len(phon_string) - 1:
                            is_separate_node = True
                            index_to_replace = None
                        else:
                            is_separate_node = False
                            index_to_replace = IndexToReplace(indices[INITIAL_INDEX], indices[INITIAL_INDEX] + len(first_changed_phoneme))
                            # print(index_to_replace)

                        # find the key in the embedded list, and change the material
                        out_lst = find_and_replace_element(out_lst, target, replacement, is_separate_node, is_initial_node, index_to_replace)
                        # print(f'\tFinal Data: {out_lst}')
                    if count - 1 in indices:
                        is_initial_node = False
                        target = f'{node}\n{phon_string}'
                        replacement = f'{node}\n{second_changed_phoneme}'
                        # find the key in the embedded list, and change the material
                        out_lst = find_and_replace_element(out_lst, target, replacement, is_separate_node, is_initial_node, index_to_replace)
                        # print(f'\tFinal Data: {out_lst}')
                        indices.remove(count - 1)

                    count += 1

    return out_lst

# ------------------------------------------------------------------------ #

def extract_final_derivation(in_lst):
    final_derivation = flatten(in_lst)
    outstring = ""
    for morpheme in final_derivation:
        if '\n' in morpheme:
            morpheme = morpheme.split('\n')
            outstring += morpheme[LAST_INDEX]

    return outstring

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- READ IN FILES --- #
# ---------------------------- #

def read_psr(folder):
    """
    Store Phrase Structure Rules from file as dictionary
    First line is the starting node
    """
    file_path = os.path.join(folder, "psr.txt")
    out_dict = {}
    try:
        with open(file_path, "r") as file:
            for i, line in enumerate(file):
                if i == 0:
                    top_node = [line.strip()]
                else:
                    line = line.strip().split(',')
                    out_dict[line[INITIAL_INDEX]] = line[SECOND_INDEX:]
    except FileNotFoundError:
        print(f"Error: 'psr.txt' file not found in the input folder '{folder}'.")
        sys.exit(1)
    
    # convert nodes which can be further expanded into lists
    for key, value in out_dict.items():
        for index, node in enumerate(value):
            if node in list(out_dict.keys()):
                out_dict[key][index] = [node]

    return top_node, out_dict

# ------------------------------------------------------------------------ #

def read_scope(folder):
    """
    Return scope and any epenthesis vowels for reduplicants
    """
    file_path = os.path.join(folder, "scope.txt")
    scope = ''

    try:
        with open(file_path, "r") as file:
            for i, line in enumerate(file):
                line = line.strip()
                if i == INITIAL_INDEX:
                    scope = line
                

    except FileNotFoundError:
        print(f"Error: 'vi_rules.txt' file not found in the input folder '{folder}'.")
        sys.exit(1)


    return scope

# ------------------------------------------------------------------------ #

def read_vi_rules(folder):
    """
    Store VI Rules from file as dictionary
    """
    file_path = os.path.join(folder, "vi_rules.txt")
    out_dict = {}
    list_of_dicts = []
    current_list = []

    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()
                if line:
                    line = line.split(',')
                    key = line[INITIAL_INDEX]
                    value_lst = line[SECOND_INDEX:]
                    if key not in out_dict:
                        out_dict[key] = []
                    out_dict[key].append({key: value_lst})
            list_of_dicts = list(out_dict.values())

    except FileNotFoundError:
        print(f"Error: 'vi_rules.txt' file not found in the input folder '{folder}'.")
        sys.exit(1)

    # all permutations of vi combinations
    list_of_dicts = generate_permutations(list_of_dicts)
    for i, item in enumerate(list_of_dicts):
        list_of_dicts[i] = flatten_list_of_dicts(item)

    return list_of_dicts

# ------------------------------------------------------------------------ #

def read_phonological_rules(folder):
    """
    Store general phonological rules from file as dictionary
    """
    file_path = os.path.join(folder, "phono_rules.txt")
    out_dict = {}
    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()
                if line:
                    line = line.split(',')
                    key = line[INITIAL_INDEX]
                    value = line[SECOND_INDEX:]
                    out_dict[key] = value

    except FileNotFoundError:
        print(f"Error: 'phono_rules.txt' file not found in the input folder '{folder}'.")
        sys.exit(1)
    return out_dict

# ------------------------------------------------------------------------ #

def read_redup_nodes(folder):
    """
    Reduplication file containing all nodes that the reduplicant phrase can dominate
    File is a one column list of phrases
    """
    file_path = os.path.join(folder, "red.txt")
    out_list = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip().split(',')
                out_list.append(line)
    except FileNotFoundError:
        print(f"Error: 'psr.txt' file not found in the input folder '{folder}'.")
        sys.exit(1)

    return out_list

# ------------------------------------------------------------------------ #

def read_evaluation_file(folder):
    file_path = os.path.join(folder, "eval.txt")
    out_list = []
    try:
        with open(file_path, "r") as file:
            for line in file:
                line = line.strip()
                if line:
                    out_list.append(line)
        return out_list
    except:
        return None

# ------------------------------------------------------------------------ #

# ---------------------------- #
# --- SAVE OUTPUT --- #
# ---------------------------- #

def save_svg_file(structure, filename, output_folder):
    """
    Save svg file 
    """
    output_filename = f'{output_folder}/{filename}.svg'
    structure = list_to_tuple(structure)
    structure = svgling.draw_tree(structure)
    structure.get_svg().saveas(output_filename)

# ------------------------------------------------------------------------ #

def save_output_txt_file(all_words, output_folder):
    """
    Save txt file of final words
    """
    output_filename = f'{output_folder}/all_words.txt'
    is_subtract_index = False

    with open(output_filename, 'w') as out_file:
        for i, word in enumerate(all_words):
            index = i
            if word != '--- reduplicated words ---':
                if is_subtract_index:
                    index = i - 1
                outstring = f'{index}. {word}\n'
            else:
                outstring = f'{word}\n'
                is_subtract_index = True
            out_file.write(outstring)

# ------------------------------------------------------------------------ #

def evaluation_of_words(all_words, evaluation_words):
    """
    Check whether all words match words specified in evalation file
    """
    all_words.remove('--- reduplicated words ---')
    print_header = True
    passed_evaluation = True
    # check if all_words are in evaluation_words
    for word in all_words:
        if word not in evaluation_words:
            if print_header:
                print('--- Words produced by script which are not evaluation file ---')
                print_header = False
                passed_evaluation = False
            print(word)
    
    print_header = True
    for word in evaluation_words:
        if word not in all_words:
            if print_header:
                print('--- Words in evaluation file which are not produced by script ---')
                print_header = False
                passed_evaluation = False
            print(word)

    if passed_evaluation:
        print('success! Evaluation passed.')
    return None

# ------------------------------------------------------------------------ #
# ------------ MAIN FUNCTION ------------ #
# ------------------------------------------------------------------------ #
def main():
    """
    Automatically parse patterns in reduplication, via a Distributed Morphology Framework
    """
    # ------ read in user config files ------ #
    args = parse_arguments()
    # --- read in custom files --- #
    syntactic_base, all_psr = read_psr(args.inputFolder)
    all_vi_rules = read_vi_rules(args.inputFolder)
    scope = read_scope(args.inputFolder)
    phonological_rules = read_phonological_rules(args.inputFolder)
    # evaluation file is optional
    evaluation_words = read_evaluation_file(args.inputFolder)
    all_words = []

    # --- nodes that REDP can dominate --- #
    dominated_nodes = read_redup_nodes(args.inputFolder)
    environment = ''
    for item in dominated_nodes:
        possible_environment = item[SECOND_INDEX]
        epenthesis = item[THIRD_INDEX]
        if possible_environment:
            environment = possible_environment

    # ------ generate base and reduplicant structures ------ #
    # base structure
    syntactic_base = create_base_structure(syntactic_base, all_psr)
    # ------ Insert VI Rules for Base Structure ------ #
    all_base_vi_lst = []

    # each permutation of vi rules
    for vi_rules in all_vi_rules:
    # insert VI rules at each level of the structure
        base_vi_lst = apply_vi_rules(syntactic_base, vi_rules, phonological_rules, scope, epenthesis, environment)
        all_base_vi_lst.append(base_vi_lst)

    count = 0
    # save each word and step as a .svg file
    for i, word in enumerate(all_base_vi_lst):
        # each step
        for j, step in enumerate(word):
            output_filename = f'base_word_{count:02d}_step_{j:02d}'
            # save the phonological output
            if j == len(word) - 1:
                output_filename += '_FINAL'
                final_word = extract_final_derivation(step)
                all_words.append(final_word)
            step = remove_stars_from_structure(step)
            save_svg_file(step, output_filename, args.outputFolder)
        count += 1

    number_of_words = len(all_words)
    outstring = '--- reduplicated words ---'
    all_words.append(outstring)
    all_redup_vi_lst = []
    # --- Insert VI Rules for Reduplicant Structure --- #
    # reduplicant variants
    for vi_rules in all_vi_rules:
        all_redup_vi_lst = []
        # generate reduplicant forms
        root = vi_rules['V'][LAST_INDEX]
        all_syntactic_redup = reduplicate_base_structure(syntactic_base, dominated_nodes, root)
        for i, redup_variant in enumerate(all_syntactic_redup):
            # insert VI rules at each level of this reduplicant level
            redup_vi_lst = apply_vi_rules(redup_variant, vi_rules, phonological_rules, scope, epenthesis, environment)
            all_redup_vi_lst.append(redup_vi_lst)

        # save each word and step of the variant as a .svg file
        for j, word in enumerate(all_redup_vi_lst):
            for k, step in enumerate(word):
                # print(k, step)
                current_number_of_words = count + number_of_words
                output_filename = f'redup_word_{count:02d}_variant_{j:02d}_step_{k:02d}'
                if k == len(word) - 1:
                    output_filename += '_FINAL'
                    final_word = extract_final_derivation(step)
                    all_words.append(final_word)
                    # print(f'***final_word: {final_word}')

                step = remove_stars_from_structure(step)
                save_svg_file(step, output_filename, args.outputFolder)
            count += 1
    save_output_txt_file(all_words, args.outputFolder)

    if evaluation_words:
        evaluation_of_words(all_words, evaluation_words)

if __name__ == "__main__":
    main()