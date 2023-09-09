# Reduplication in Distributed Morphology
This script generates reduplicated words, within a Distributed Morphology framework. It produces step-by-step derivations of the Vocabulary Insertion process, saved as .svg files containing the syntax tree.

## Files Required
The script requires a folder, containing language-specific information on the reduplication pattern of the desired language. 
The name of this folder is the name of the language.

Within the folder, there are three files:
1. vi_rules.txt
	* A list of vocabulary insertion rules.
	* Three column file, separated by commas
	head,value,phonological string
	All terminal nodes must be included in this file (even if the phonological string is empty).
	All nodes grouped together (i.e. all "T" morphemes in one section).
	
2. psr.txt
	* A list of phrase structure rules, containing the mother node and daughter nodes it can attach to.
	Must be binary or unary branching.
	* First row must contain the starting node.
	Phrases cannot contain new line characters.

3. red.txt
	* A list of all nodes redP can attach to.
	* The first row specifies the scope of the reduplicant.
	* If redP can attach to nodes only in a specific phonological environment, this is specified in the second column.


4. scope.txt
	* Specifies the scope (prosodic template) and any epenthesis vowels for the reduplicant
	* First row is the scope
		* Either 'bisyllabic' for bisyllabic template (with no coda), or empty for full reduplication
	* Second row is the epenthesis vowel

5. phono_rules.txt
	* Specifies general language-specific phonological rules
	* Three column .csv file, separated by commas
	* First column states the string of phonemes to be changed
	* Second column states the start of the string that is changed
	* Third column states the end of the string is not changed

