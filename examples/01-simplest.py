TARGET = tsf('cage.aiff', thresh=-26, offsetRise=1.2)

CORPUS = [
csf('lachenmann.aiff'),
] # CORPUS documented in 04-corpus.py

SEARCH = [
spass('ratio_limit', d('effDur-seg'), minratio=0.8, maxratio=1.2),
spass('closest', d('mfccs-seg'))
] # SEARCH documented in 02-searching.py

SUPERIMPOSE = si(maxSegment=4) # SUPERIMPOSE documented in 03-superimposition.py

