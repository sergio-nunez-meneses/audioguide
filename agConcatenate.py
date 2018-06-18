#!/usr/bin/env python
############################################################################
## This software is distributed for free, without warranties of any kind. ##
## Send bug reports or suggestions to hackbarth@gmail.com                 ##
############################################################################


import sys, os, audioguide
defaultpath, libpath = audioguide.setup(os.path.dirname(__file__))
opspath = audioguide.optionsfiletest(sys.argv)
sys.path.append(libpath)
# import the rest of audioguide's submodules
from audioguide import sfSegment, concatenativeClasses, simcalc, userinterface, util, descriptordata, anallinkage, html5output
# import all other modules
import numpy as np
try:
	import json as json
except ImportError:
	import simplejson as json



from optparse import OptionParser
parser = OptionParser(usage="usage: %prog [options] configfile")
parser.set_defaults(OUTPUT_FILE='')
parser.add_option("-o", "--printoptions", action="store_true", dest="PRINT_OPTIONS", default=False, help="print all AG options and exit")
(options, args) = parser.parse_args()
if options.PRINT_OPTIONS:
	sys.exit(0)



###########################################
## LOAD OPTIONS AND SETUP SDIF-INTERFACE ##
###########################################
ops = concatenativeClasses.parseOptions(opsfile=opspath, defaults=defaultpath, scriptpath=os.path.dirname(__file__))
p = userinterface.printer(ops.VERBOSITY, os.path.dirname(__file__), ops.LOG_FILEPATH)
p.printProgramInfo(audioguide.__version__)
AnalInterface = ops.createAnalInterface(p)
html = html5output.htmloutput()
p.middleprint('SOUNDFILE CONCATENATION')


############
## TARGET ##
############
html.logsection( "TARGET" )
tgt = sfSegment.target(ops.TARGET)
tgt.initAnal(AnalInterface, ops, p)
if len(tgt.segs) == 0:
	util.error("TARGET FILE", "no segments found!  this is rather strange.  could your target file %s be digital silence??"%(tgt.filename))
html.log("TARGET SEGMENTATION: found %i segments with an average length of %.3f seconds"%(len(tgt.segs), np.average(tgt.seglengths)))
#######################
## target label file ##
#######################
if ops.TARGET_SEGMENT_LABELS_FILEPATH != None:
	tgt.writeSegmentationFile(ops.TARGET_SEGMENT_LABELS_FILEPATH)
	html.log( "TARGET: wrote segmentation label file %s"%ops.TARGET_SEGMENT_LABELS_FILEPATH )
#############################
## target descriptors file ##
#############################
if ops.TARGET_DESCRIPTORS_FILEPATH != None:
	outputdict = tgt.whole.desc.getdict()
	outputdict['frame2second'] = AnalInterface.f2s(1)
	fh = open(ops.TARGET_DESCRIPTORS_FILEPATH, 'w')
	json.dump(outputdict, fh)
	fh.close()
	html.log("TARGET: wrote descriptors to %s"%(ops.TARGET_DESCRIPTORS_FILEPATH))
##############################
## target descriptor graphs ##
##############################
if ops.TARGET_PLOT_DESCRIPTORS_FILEPATH != None:
	tgt.plotMetrics(ops.TARGET_PLOT_DESCRIPTORS_FILEPATH, AnalInterface, p)
###############################
## target segmentation graph ##
###############################
if ops.TARGET_SEGMENTATION_GRAPH_FILEPATH != None:
	tgt.plotSegmentation(ops.TARGET_SEGMENTATION_GRAPH_FILEPATH, AnalInterface, p)

descriptors = []
dnames = []
for dobj in AnalInterface.requiredDescriptors:
	if dobj.seg or dobj.name in ['power']: continue
	d = np.array(tgt.whole.desc[dobj.name][:])
	d -= np.min(d)
	d /= np.max(d)
	d = np.around(d, 2)
	
	descriptors.append(d)
	dnames.append(dobj.name)
html.jschart_timeseries(yarray=np.array([AnalInterface.f2s(i) for i in range(tgt.whole.lengthInFrames)]), xarrays=descriptors, ylabel='time in seconds', xlabels=dnames)


############
## CORPUS ##
############
html.logsection( "CORPUS" )
cps = concatenativeClasses.corpus(ops.CORPUS, ops.CORPUS_GLOBAL_ATTRIBUTES, ops.RESTRICT_CORPUS_SELECT_PERCENTAGE_BY_STRING, AnalInterface, p)




#cps.postLimitSegmentNormList.sort()
#for tgtseg in cps.postLimitSegmentNormList:
#	tgtseg.desc['f0-seg'].get(0, None)
#	print tgtseg.segmentStartSec, tgtseg.desc['f0-seg'].get(0, None)
##	for fidx, f0 in enumerate(tgtseg.desc['f0']):
##		print fidx, f0, tgtseg.desc['inharmonicity'][fidx]
#sys.exit()


###################
## NORMALIZATION ##
###################
html.logsection( "NORMALIZATION" )


if ops.NORMALIZATION_METHOD == 'standard':
	html.log( "<table><tr><th>descriptor</th><th>target mean</th><th>target stddev</th><th>corpus mean</th><th>corpus stddev</th><th>freedom</th></tr>", p=False )
	for dobj in AnalInterface.normalizeDescriptors:
		if dobj.norm == 1:
			# normalize both together
			allsegs = tgt.segs + cps.postLimitSegmentNormList
			tgtStatistics = cpsStatistics = sfSegment.getDescriptorStatistics(allsegs, dobj, stdDeltaDegreesOfFreedom=ops.NORMALIZATION_DELTA_FREEDOM)
			sfSegment.applyDescriptorNormalisation(allsegs, dobj, tgtStatistics)
		elif dobj.norm == 2:
			# normalize target
			tgtStatistics = sfSegment.getDescriptorStatistics(tgt.segs, dobj, stdDeltaDegreesOfFreedom=ops.NORMALIZATION_DELTA_FREEDOM)
			sfSegment.applyDescriptorNormalisation(tgt.segs, dobj, tgtStatistics)
			# normalize corpus
			cpsStatistics = sfSegment.getDescriptorStatistics(cps.postLimitSegmentNormList, dobj, stdDeltaDegreesOfFreedom=ops.NORMALIZATION_DELTA_FREEDOM)
			sfSegment.applyDescriptorNormalisation(cps.postLimitSegmentNormList, dobj, cpsStatistics)
		html.log( "<tr><td>%s</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%.3f</td><td>%.3f</td></tr>"%(dobj.name, tgtStatistics['mean'], tgtStatistics['stddev'], cpsStatistics['mean'], cpsStatistics['stddev'], ops.NORMALIZATION_DELTA_FREEDOM), p=False )
	html.log( "</table>" , p=False)

elif ops.NORMALIZATION_METHOD == 'cluster':
	clusterObj = descriptordata.clusterAnalysis(ops.CLUSTER_MAPPING, tgt.segs, cps.postLimitSegmentNormList, os.path.dirname(__file__))
	tgtClusts, cpsClusts = clusterObj.getClusterNumbers()
	clusteredSegLists = []
	for segs, clustList in [(tgt.segs, tgtClusts), (cps.postLimitSegmentNormList, cpsClusts)]:
		for cidx in clustList:
			clusteredSegLists.append([seg for seg in segs if seg.cluster == cidx])
	for segList in clusteredSegLists:
		if len(segList) == 0: continue
		for dobj in AnalInterface.normalizeDescriptors:
			stats = sfSegment.getDescriptorStatistics(segList, dobj, stdDeltaDegreesOfFreedom=ops.NORMALIZATION_DELTA_FREEDOM)
			sfSegment.applyDescriptorNormalisation(segList, dobj, stats)




scatterRaw = {'tgt': {}, 'cps': {}}
for dname in [dobj.name for dobj in AnalInterface.requiredDescriptors if dobj.seg]:
	scatterRaw['tgt'][dname] = []
	scatterRaw['cps'][dname] = []


scatterNorm = {'tgt': {}, 'cps': {}}
for dname in [dobj.name for dobj in AnalInterface.normalizeDescriptors if dobj.seg]:
	scatterNorm['tgt'][dname] = []
	scatterNorm['cps'][dname] = []

for tidx, ts in enumerate(tgt.segs):
	for dname in scatterRaw['tgt'].keys():
		scatterRaw['tgt'][dname].append(ts.desc[dname].get(0, None))
	for dname in scatterNorm['tgt'].keys():
		scatterNorm['tgt'][dname].append(ts.desc[dname].getnorm(0, None))

for cidx, cs in enumerate(cps.postLimitSegmentNormList):
	for dname in scatterRaw['cps'].keys():
		scatterRaw['cps'][dname].append(cs.desc[dname].get(0, None))
	for dname in scatterNorm['cps'].keys():
		scatterNorm['cps'][dname].append(cs.desc[dname].get(0, None))


html.addScatter2dAxisChoice(scatterRaw, name='Unnormalized Descriptor Data', axisdefaults=['effDur-seg', 'power-seg'])
#html.addScatter2dAxisChoice(scatterNorm, name='Normalized Descriptor Data', axisdefaults=[AnalInterface.normalizeDescriptors[0], AnalInterface.normalizeDescriptors[1]])
	

	
	
		
	
	
##############################
## initialise concatenation ##
##############################
html.logsection( "CONCATENATION" )
tgt.setupConcate(AnalInterface)
AnalInterface.done()
distanceCalculations = simcalc.distanceCalculations(ops.SUPERIMPOSE, ops.RANDOM_SEED, AnalInterface, p)
superimp = concatenativeClasses.SuperimposeTracker(tgt.lengthInFrames, len(tgt.segs), ops.SUPERIMPOSE.overlapAmpThresh, ops.SUPERIMPOSE.peakAlign, ops.SUPERIMPOSE.peakAlignEnvelope, len(ops.CORPUS), ops.RESTRICT_CORPUS_OVERLAP_BY_STRING, p)
cps.setupConcate(tgt, AnalInterface)
outputEvents = []

#######################################
### sort segments by power if needed ##
#######################################
import operator
if ops.SUPERIMPOSE.searchOrder == 'power':
	tgt.segs = sorted(tgt.segs, key=operator.attrgetter("power"), reverse=True)
else:
	tgt.segs = sorted(tgt.segs, key=operator.attrgetter("segmentStartSec"))


#########################
## TARGET SEGMENT LOOP ##
#########################
p.startPercentageBar(upperLabel="CONCATINATING", total=len(tgt.segs)+1)
for segidx, tgtseg in enumerate(tgt.segs):
	segSeek = 0
	p.percentageBarNext()
	while True:
		##############################################################
		## check to see if we are done with this particular segment ##
		##############################################################
		if segSeek >= tgtseg.lengthInFrames: break 
		########################################
		## run selection superimposition test ##
		########################################
		tif = tgtseg.segmentStartFrame+segSeek
		if tif >= tgt.lengthInFrames: break
		timeInSec = AnalInterface.f2s(tif)
		tgtsegdur =  tgtseg.segmentDurationSec - AnalInterface.f2s(segSeek)
		segidxt = superimp.test('segidx', segidx, ops.SUPERIMPOSE.minSegment, ops.SUPERIMPOSE.maxSegment)
		overt = superimp.test('overlap', tif, ops.SUPERIMPOSE.minOverlap, ops.SUPERIMPOSE.maxOverlap)
		onsett = superimp.test('onset', tif, ops.SUPERIMPOSE.minOnset, ops.SUPERIMPOSE.maxOnset)
		trigVal = tgtseg.thresholdTest(segSeek, AnalInterface.tgtOnsetDescriptors)
		trig = trigVal >= tgt.segmentationThresh
		####################################################
		# skip selecting if some criteria doesn't match!!! #
		####################################################
		if 'notok' in [onsett, overt, segidxt]:
			if segidxt == 'notok':
				superimp.skip('maximum selections this segment', superimp.cnt['segidx'][segidx], timeInSec)
			if onsett == 'notok':
				superimp.skip('maximum onsets at this time', superimp.cnt['onset'][tif], timeInSec)
			if overt == 'notok':
				superimp.skip('maximum overlapping selections', superimp.cnt['overlap'][tif], timeInSec)
			segSeek += ops.SUPERIMPOSE.incr
			continue # next frame
		##############################################################
		## see if a selection should be forced without thresholding ##
		##############################################################
		if 'force' not in [onsett, overt, segidxt]: # test for amplitude threshold
			if not trig:
				superimp.skip('target too soft', trigVal, timeInSec)
				segSeek += ops.SUPERIMPOSE.incr
				continue # not loud enough, next frame
		##############################
		## get valid corpus handles ##
		##############################
		validSegments = cps.evaluateValidSamples(tif, timeInSec, tgtseg.idx, ops.ROTATE_VOICES, ops.VOICE_PATTERN, ops.VOICE_TO_ONSET_MAPPING, ops.CLUSTER_MAPPING, tgtseg.cluster, superimp)
		if len(validSegments) == 0:
			superimp.skip('no corpus sounds made it past restrictions and limitations', None, timeInSec)
			segSeek += ops.SUPERIMPOSE.incr
			continue		
		distanceCalculations.setCorpus(validSegments)
		################################################
		## search and see if we find a winning sample ##
		################################################
		returnBool = distanceCalculations.executeSearch(tgtseg, segSeek, ops.SEARCH, ops.SUPERIMPOSE, ops.RANDOMIZE_AMPLITUDE_FOR_SIM_SELECTION)
		if not returnBool: # nothing valid, so skip to new frame...
			superimp.skip('no corpus sounds made it through the search passes', None, timeInSec)
			segSeek += ops.SUPERIMPOSE.incr
			continue
		###################################################
		## if passing this point, picking a corpus sound ##
		###################################################
		superimp.pick(trig, trigVal, onsett, overt, segidxt, timeInSec)
		selectCpsseg = distanceCalculations.returnSearch()
		######################################
		## MODIFY CHOSEN SAMPLES AMPLITUDE? ##
		######################################
		minLen = min(tgtseg.lengthInFrames-segSeek, selectCpsseg.lengthInFrames)	
		if selectCpsseg.postSelectAmpBool:
			if selectCpsseg.postSelectAmpMethod == "lstsqr":
				try:
					leastSqrWholeLine = (np.linalg.lstsq(np.vstack([selectCpsseg.desc['power'][:minLen]]).T, np.vstack([tgtseg.desc['power'][:minLen]]).T)[0][0][0])
				except np.linalg.linalg.LinAlgError: # in case of incompatible dimensions
					leastSqrWholeLine = 0
					pass
			elif selectCpsseg.postSelectAmpMethod in ["power-seg", "power-mean-seg"]:
				tgtPower = tgtseg.desc[selectCpsseg.postSelectAmpMethod].get(segSeek, None)
				cpsPower = selectCpsseg.desc[selectCpsseg.postSelectAmpMethod].get(0, None)
				sourceAmpScale = tgtPower/cpsPower			
			###################
			## fit to limits ##
			###################
			if sourceAmpScale < util.dbToAmp(selectCpsseg.postSelectAmpMin):
				sourceAmpScale = util.dbToAmp(selectCpsseg.postSelectAmpMin)
			elif sourceAmpScale > util.dbToAmp(selectCpsseg.postSelectAmpMax):
				sourceAmpScale = util.dbToAmp(selectCpsseg.postSelectAmpMax)
		else: # nothing
			sourceAmpScale = 1
		# apply amp scaling
		sourceAmpScale *= util.dbToAmp(ops.OUTPUT_GAIN_DB)
		sourceAmpScale *= util.dbToAmp(selectCpsseg.envDb)
		###################$###########################
		## subtract power and update onset detection ##
		###################$###########################
		if ops.SUPERIMPOSE.calcMethod != None:
			#oneInCorpusLand = (1-cps.powerStats['mean'])/cps.powerStats['stddev']
			#normalizationPowerRatio = (oneInCorpusLand*tgt.powerStats['stddev'])+tgt.powerStats['mean']
			
			preSubtractPeak = util.ampToDb(np.max(tgtseg.desc['power'][segSeek:segSeek+minLen]))
			rawSubtraction = tgtseg.desc['power'][segSeek:segSeek+minLen]-(selectCpsseg.desc['power'][:minLen]*sourceAmpScale*ops.SUPERIMPOSE.subtractScale)
			tgtseg.desc['power'][segSeek:segSeek+minLen] = np.clip(rawSubtraction, 0, sys.maxint) # clip it so its above zero
			postSubtractPeak = util.ampToDb(np.max(tgtseg.desc['power'][segSeek:segSeek+minLen]))
			#html.log("\tsubtracted %i corpus frames from target's amplitude -- original peak %.1fdB, new peak %.1fdB"%(minLen, preSubtractPeak, postSubtractPeak))
			
			# recalculate onset envelope
			SdifDescList, ComputedDescList, AveragedDescList = tgtseg.desc.getDescriptorOrigins() 
			for dobj in ComputedDescList:
				if dobj.describes_energy and dobj.name != 'power':
					tgtseg.desc[dobj.name] = descriptordata.DescriptorComputation(dobj, tgtseg, None, None)
			for d in AveragedDescList:
				tgtseg.desc[d.name].clear()
		#####################################
		## mix chosen sample's descriptors ##
		#####################################
		if ops.SUPERIMPOSE.calcMethod == "mixture":
			tgtseg.mixSelectedSamplesDescriptors(selectCpsseg, sourceAmpScale, segSeek, AnalInterface)
		#################################
		## append selected corpus unit ##
		#################################
		transposition = util.getTransposition(tgtseg, selectCpsseg)
		cps.updateWithSelection(selectCpsseg, timeInSec, segidx)
		cpsEffDur = selectCpsseg.desc['effDurFrames-seg'].get(0, None)
		maxoverlaps = np.max(superimp.cnt['overlap'][tif:tif+minLen])
		eventTime = (timeInSec*ops.OUTPUT_TIME_STRETCH)+ops.OUTPUT_TIME_ADD
		outputEvents.append( concatenativeClasses.outputEvent(selectCpsseg, eventTime, util.ampToDb(sourceAmpScale), transposition, tgtseg, maxoverlaps, tgtsegdur, tgtseg.idx, ops.CSOUND_STRETCH_CORPUS_TO_TARGET_DUR, AnalInterface.f2s(1), ops.CSOUND_RENDER_DUR, ops.CSOUND_ALIGN_PEAKS) )
		
		corpusname = os.path.split(cps.data['vcToCorpusName'][selectCpsseg.voiceID])[1]
		superimp.increment(tif, tgtseg.desc['effDurFrames-seg'].get(segSeek, None), segidx, selectCpsseg.voiceID, selectCpsseg.desc['power'], distanceCalculations.returnSearchPassText(), corpusname, selectCpsseg.filename)
		tgtseg.numberSelectedUnits += 1

		printLabel = "searching @ %.2f x %i"%(timeInSec, maxoverlaps+1)
		printLabel += ' '*(24-len(printLabel))
		printLabel += "search pass lengths: %s"%('  '.join(distanceCalculations.lengthAtPasses))
		p.percentageBarNext(lowerLabel=printLabel, incr=0)

p.percentageBarClose(txt='Selected %i events'%len(outputEvents))

#if ops.PRINT_SIM_SELECTION_HISTO:
#	p.printListLikeHistogram('Simultaneous Selection Histogram', ["%i notes"%(v) for v in superimp.cnt['segidx']])
#if ops.PRINT_SELECTION_HISTO:
#	p.printListLikeHistogram('Corpus Selection Histogram', superimp.cnt['cpsnames'])



#html.addchart(["%i notes"%(v) for v in superimp.cnt['segidx']], type='barchart', title='Simultaneous Selection Histogram')


#html.addchart(superimp.cnt['cpsnames'], type='barchart', title='Corpus Selection Histogram')


#html.addchart(list(tgt.whole.desc['power']), type='line', title='Target Amplitude')





#####################################
## sort outputEvents by start time ##
#####################################
outputEvents.sort(key=lambda x: x.timeInScore)


###########################
## temporal quantization ##
###########################
concatenativeClasses.quantizeTime(outputEvents, ops.OUTPUT_QUANTIZE_TIME_METHOD, float(ops.OUTPUT_QUANTIZE_TIME_INTERVAL), p)

html.logsection( "OUTPUT FILES" )
allusedcpsfiles = list(set([oe.filename for oe in outputEvents]))



######################
## dict output file ##
######################
if ops.DICT_OUTPUT_FILEPATH != None:
	output = {}
	output['opsfilename'] = ops.opsfilehead
	output['opsfiledata'] = ops.opsfileAsString
	# make target segment dict list
	tgt.segs.sort(key=operator.attrgetter('segmentStartSec'))
	tgtSegDataList = []
	for ts in tgt.segs:
		thisSeg = {'startSec': ts.segmentStartSec, 'endSec': ts.segmentEndSec}
		thisSeg['power'] = ts.desc['power-seg'].get(0, None)
		thisSeg['numberSelectedUnits'] = ts.numberSelectedUnits
		thisSeg['has_been_mixed'] = ts.has_been_mixed
		tgtSegDataList.append(thisSeg)
	# finish up
	output['target'] = {'filename': tgt.filename, 'sfSkip': tgt.startSec, 'duration': tgt.endSec-tgt.startSec, 'segs': tgtSegDataList, 'fileduation': AnalInterface.rawData[tgt.filename]['info']['lengthsec'], 'chn': AnalInterface.rawData[tgt.filename]['info']['channels']} 
	output['corpus_file_list'] = list(set(allusedcpsfiles))
	output['selectedEvents'] = [oe.makeDictOutput() for oe in outputEvents]
	fh = open(ops.DICT_OUTPUT_FILEPATH, 'w')
	json.dump(output, fh)
	fh.close()
	html.log( "Wrote JSON dict file %s\n"%ops.DICT_OUTPUT_FILEPATH )

#####################################
## maxmsp list output pour gilbert ##
#####################################
if ops.MAXMSP_OUTPUT_FILEPATH != None:
	output = {}
	output['target_file'] = [tgt.filename, tgt.startSec*1000., tgt.endSec*1000.]
	output['events'] = [oe.makeMaxMspListOutput() for oe in outputEvents]
	output['corpus_files'] = allusedcpsfiles
	fh = open(ops.MAXMSP_OUTPUT_FILEPATH, 'w')
	json.dump(output, fh)
	fh.close()
	html.log( "Wrote MAX/MSP JSON lists to file %s\n"%ops.MAXMSP_OUTPUT_FILEPATH )
	
######################
## midi output file ##
######################
if ops.MIDI_FILEPATH != None:
	import midifile
	MyMIDI = midifile.MIDIFile(1)
	MyMIDI.addTrackName(0, 0., "AudioGuide Track")
	MyMIDI.addTempo(0, 0., ops.MIDIFILE_TEMPO)
	temposcalar = ops.MIDIFILE_TEMPO/60.
	for oe in outputEvents:
		MyMIDI.addNote(0, 0, oe.midiPitch, oe.timeInScore*temposcalar, oe.duration*temposcalar, oe.midiVelocity)
	binfile = open(ops.MIDI_FILEPATH, 'wb')
	MyMIDI.writeFile(binfile)
	binfile.close()
	html.log( "Wrote MIDIfile %s\n"%ops.MIDI_FILEPATH )

###################################
## superimpose label output file ##
###################################
if ops.OUTPUT_LABEL_FILEPATH != None:
	fh = open(ops.OUTPUT_LABEL_FILEPATH, 'w')
	fh.write( ''.join([ oe.makeLabelText() for oe in outputEvents ]) )
	fh.close()
	html.log( "Wrote superimposition label file %s\n"%ops.OUTPUT_LABEL_FILEPATH )

#######################################
## corpus segmented features as json ##
#######################################
if ops.CORPUS_SEGMENTED_FEATURES_JSON_FILEPATH != None:
	fh = open(ops.CORPUS_SEGMENTED_FEATURES_JSON_FILEPATH, 'w')
	alldata = {}
	for c in cps.postLimitSegmentNormList:
		descs = {}
		for name, obj in c.desc.nameToObjMap.items():
			if name.find('-seg') != -1:
				descs[ name ] = obj.get(0, c.desc.len)
		alldata[(c.filename+'@'+str(c.segmentStartSec))] = descs
	json.dump(alldata, fh)
	fh.close()
	html.log( "Wrote corpus segmented features file %s\n"%ops.CORPUS_SEGMENTED_FEATURES_JSON_FILEPATH )


######################
## lisp output file ##
######################
if ops.LISP_OUTPUT_FILEPATH != None:
	fh = open(ops.LISP_OUTPUT_FILEPATH, 'w')
	fh.write('(' + ''.join([ oe.makeLispText() for oe in outputEvents ]) +')')
	fh.close()
	html.log( "Wrote lisp output file %s\n"%ops.LISP_OUTPUT_FILEPATH )

########################################
## data from segmentation file output ##
########################################
if ops.DATA_FROM_SEGMENTATION_FILEPATH != None:
	fh = open(ops.DATA_FROM_SEGMENTATION_FILEPATH, 'w')
	for line in [oe.makeSegmentationDataText() for oe in outputEvents]:
		fh.write(line)
	fh.close()
	html.log( "Wrote data from segmentation file to textfile %s\n"%ops.DATA_FROM_SEGMENTATION_FILEPATH )

########################
## csound output file ##
########################
if ops.CSOUND_CSD_FILEPATH != None:
	import csoundinterface as csd
	maxOverlaps = np.max([oe.simSelects for oe in outputEvents])
	#csSco = csd.makeFtableFromDescriptor(tgt.whole.desc['power'], 'power', AnalInterface.f2s(1), ops.CSOUND_SR, ops.CSOUND_KSMPS)+'\n\n'
	csSco = 'i2  0.  %f  %f  "%s"  %f\n\n'%(tgt.endSec-tgt.startSec, tgt.whole.envDb, tgt.filename, tgt.startSec)
	
	# just in case that there are negative p2 times!
	minTime = min([ oe.timeInScore for oe in outputEvents ])
	if minTime < 0:
		for oe in outputEvents:
			oe.timeInScore -= minTime
	csSco += ''.join([ oe.makeCsoundOutputText(ops.CSOUND_CHANNEL_RENDER_METHOD) for oe in outputEvents ])
	csd.makeConcatenationCsdFile(ops.CSOUND_CSD_FILEPATH, ops.CSOUND_RENDER_FILEPATH, ops.CSOUND_CHANNEL_RENDER_METHOD, ops.CSOUND_SR, ops.CSOUND_KSMPS, csSco, cps.len, set([oe.sfchnls for oe in outputEvents]), maxOverlaps, bits=ops.CSOUND_BITS)
	html.log( "Wrote csound csd file %s\n"%ops.CSOUND_CSD_FILEPATH )
	if ops.CSOUND_RENDER_FILEPATH != None:
		csd.render(ops.CSOUND_CSD_FILEPATH, len(outputEvents), printerobj=p)
		html.log( "Rendered csound soundfile output %s\n"%ops.CSOUND_RENDER_FILEPATH )
	
	if True:#ops.CSOUND_NORMALIZE:
		csd.normalize(ops.CSOUND_RENDER_FILEPATH, db=ops.CSOUND_NORMALIZE_PEAK_DB)


####################
## close log file ##
####################
if ops.HTML_LOG_FILEPATH != None:
	html.writefile(ops.HTML_LOG_FILEPATH)
	
if ops.CSOUND_RENDER_FILEPATH != None and ops.CSOUND_PLAY_RENDERED_FILE:
	csd.playFile( ops.CSOUND_RENDER_FILEPATH )
		
	
