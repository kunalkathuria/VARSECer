#Identify all discordant reads
#$ Change "tid" to "ref_name"
import math
import sys
import pysam
import time
from itertools import izip

PERMUTATION_THRESH = int(sys.argv[3])#20
CALC_THRESH = int(sys.argv[6]) #500000
MATCH_PCT = float(sys.argv[7]) #0
MATCH_THRESH = float(sys.argv[5]) #.9 # RELATIVE ALIGNMENT PRECISION OF PRIMARY VS SECONDARY ALIGNMENT
PCT_THRESH = float(sys.argv[4]) #1
FILE1 = "../data/bams/aln1s.bam" # read 1 discordants
FILE2 = "../data/bams/aln2s.bam"# read 2 discordants
BAMFILE1 = sys.argv[1] #name-sorted BAM file.
BAMFILE2 = sys.argv[2] # position-sorted same BAM file.
ignoreR_FILE = sys.argv[8]
ignoreChr = sys.argv[9]
MAP_THRESH = int(sys.argv[10])
AS_THRESH = float(sys.argv[11])
MAP_THRESH_U = int(sys.argv[12])
SIG_THRESH = float(sys.argv[13])
AS_CALC_THRESH = float(sys.argv[14])
ignoreTIDList = []
chrHash = {}
BIG_NUM = 100000 # used to override thresholds for primary alignments below

def calcMeanSig(file1, file2):
   bamfile = pysam.Samfile(file2,"rb")
   summedIL = 0
   summedQL = 0
   counter = 0
   stdev = 0
   max_IL = 0
   loopCount = 0
   IL_list = []

   while counter < CALC_THRESH and loopCount < 2*CALC_THRESH:

        try:

            m1 = bamfile.next()

        except StopIteration:
            break

	#print m1.get_tag("XS")
	#last condition ensures split read will not be included in analysis because "next" may not be mate then
        if m1.is_proper_pair and not m1.is_secondary and not m1.is_supplementary and m1.get_tag("AS") > AS_CALC_THRESH*m1.infer_query_length() and m1.template_length > 0:

             #if m1.reference_start < m1.next_reference_start:
             #    minm = m1.reference_start
             #    maxm = m1.next_reference_start
             #else:
             #    maxm = m1.reference_start
             #    minm = m1.next_reference_start

	     #IL = maxm - minm
	     IL = m1.template_length
	     IL_list.append(IL)	
	     
	     if IL > max_IL:
		max_IL = IL
             summedIL+= IL
	     summedQL+= m1.infer_query_length()
             counter+= 1
	loopCount+=1
   if counter == 0 or counter ==1:
	print "Division by 0. Please check order of name-sorted and position-sorted files supplied."
	return
   meanIL = summedIL/counter
   meanQL = summedQL/counter
   #make outer IL distance	
   #meanIL+=meanQL
   #new_IL_list = [x+meanQL for x in IL_list]
   IL_list = sorted(IL_list)
   
   #"generalized" 3 sigma distance if not normal distribution, SIG_THRESH = 99.85
   DISC_D = IL_list[int(SIG_THRESH*len(IL_list)) - 1]
   print "DISC stats:", SIG_THRESH, DISC_D, len(IL_list), IL_list[-50:]
   DISC_D = DISC_D - meanIL
   bamfile.close()
   
   bamfile = pysam.Samfile(file2,"rb")
   loopCount=0
   counter=0
   while counter < CALC_THRESH and loopCount < 2*CALC_THRESH:

        try:

            m1 = bamfile.next()

        except StopIteration:
            break

	if m1.is_proper_pair and not m1.is_secondary and not m1.is_supplementary and m1.get_tag("AS") > AS_CALC_THRESH*m1.infer_query_length() and m1.template_length > 0:

	     #print str(m1)[str(m1).find("M")-3:str(m1).find("M")+1]	
	     #if m1.reference_start < m1.next_reference_start:
             #    minm = m1.reference_start
             #    maxm = m1.next_reference_start
             #else:
             #    maxm = m1.reference_start
             #    minm = m1.next_reference_start

	     #query length of mate not available (using position-sorted file)		
             #stdev+= (maxm - minm + meanQL - meanIL)**2
	     stdev+= (m1.template_length - meanIL)**2
	     counter+=1
	loopCount+=1

   bamfile.close()
   bamfile = pysam.AlignmentFile(file2,"rb")

   cov = 0
   width = 20
   counter2=0

   for pileupcolumn in bamfile.pileup():
   	cov+=pileupcolumn.n
	counter2+=1
	if counter2 > CALC_THRESH:
		break

   bamfile.close()
   stdev = stdev/counter
   stdev = stdev**(.5)
   cov=cov/counter2

   if DISC_D < 0:
        DISC_D = 3*stdev
   print meanQL, meanIL, stdev, cov, max_IL, DISC_D
   fp = open("../results/text/bam_stats.txt","w")
   fp.write("%s\n%s\n%s\n%s\n%s\n%s\n" %(meanQL, meanIL, stdev,cov, max_IL, DISC_D))
   fp.close()
   return meanQL, meanIL, stdev, DISC_D

[RDL, MEAN_D, SIG_D, DISC_dist] = calcMeanSig(BAMFILE1, BAMFILE2)
ignore_buffer =0* RDL

def formHash():

        prevTID = "*" # invalid value
        fo=open(ignoreR_FILE,"r")
        print ignoreR_FILE

        for line in fo:
                line_s = line.split()
                currentTID = line_s[0]
                if currentTID != prevTID:

                        chrHash[currentTID] = {}

                for x in range(int(line_s[1])-ignore_buffer, int(line_s[2])+ignore_buffer):
                        chrHash[currentTID][x] = 1

                prevTID = currentTID

def ignoreRead(chr_l, loc_l, chr_r, loc_r):

        if chr_l in chrHash and loc_l in chrHash[chr_l]:
                return 1

        if chr_r in chrHash and loc_r in chrHash[chr_r]:
                return 1

        return 0

def recordChr():

	f= open(ignoreChr, "r")
	for line in f:
		ignoreTIDList.append(line.split()[0])

class Cluster(object):

    def __init__(self):

       #Whether l_bound is start or end of left-aligned read (in reference) depends on orientation of read in reference
       self.l_bound=None
       self.r_bound=None
       self.l_bound_O=None # debug variable. first pair in cluster: all positions assessed relative to this one for future additions to cluster
       self.r_bound_O=None
       self.C_type=None # LR orientation: F=0, R=1
       self.Cmap_type = None # 0 if both reads map, 1 if one read maps only
       self.ltid = None
       self.rtid = None
       self.l_target = None
       self.r_target = None
       self.mapqual = -1
       self.clsmall = -1
       self.ascore1 = -1
       self.ascore2 = -1

    def __str__(self):
        return "%s %s %s %s %s %s %s %s %s %s %s" % (self.ltid, self.l_bound, self.rtid, self.r_bound, self.C_type, self.l_target, self.r_target, self.ascore1, self.ascore2, self.clsmall, self.mapqual)

def findTotalNMatches(al):

	MDtag_pos = str(al).find("MD",10) + 6
	temp = str(al)[MDtag_pos:].find(")")
	MDtag = str(al)[MDtag_pos:MDtag_pos +temp-1]
	
	# MD tag is set for perfect matches, so if not set, dubious
	if MDtag_pos == 5:
		return 0,0

	integers = "0123456789"
	n_matches = 0
	prev = "0"
	n_subs = 0
	for string in MDtag:
		if string in integers:
			prev+= string
		else:
			n_matches+= int(prev)
			prev = "0"
			n_subs+=1

	n_matches+=int(prev)

	if n_matches > 0:
		return n_matches, float(n_matches)/float(n_matches + n_subs)
	else:
		return 0,0

def calcXAstats(tagXA):

	tagP = tagXA.split(",")
	ch = tagP[0]
	fr = -1
	if tagP[1][0] == "+":
		fr = 0
	elif tagP[1][0] == "-":
		fr = 1
	start = int(tagP[1][1:])
	cigstr = tagP[2]

	MISM_P = 1 #mismatch penalty
        integers = "0123456789"
        score = 0
        prev = "0"
	QL = 0
	nm = 0
	nmm = int(tagP[3])
        for string in cigstr:
                if string in integers:
                        prev+= string
                elif string == "M":
                        score+= int(prev)
			nm+= int(prev)
			QL+= int(prev)
                        prev = "0"
		elif string == "I" or string == "D":
			score= score - 6 - int(prev)
			if string == "I":
				QL+= int(prev)
			else:
				nm+= int(prev)
			nmm = nmm-int(prev)
			prev = "0"
		else:
			QL+= int(prev)
			prev = "0"

	#print "Score w/o penalty is:", score
	end = start + nm
	score-= MISM_P*nmm
	#print "Score w/ penalty is:", score, "Nmm:", nmm

	if score < 0:
		score = 0
	if QL < 0:
		QL = 0

	return ch, start, end, 0, -1, fr, score, QL

def findNumberMatches(cigartups):
    nummatches = 0
    if cigartups == None:
        return 0
    for op,oplen in cigartups:
        if op in [0,1,7]:
            nummatches += int(oplen)

    return nummatches

def FormDiscordant(al1, al2, DList1, DList2):

    counter = 0
    OUTER_D = MEAN_D # non-discordant default value. safe.
    Tag1_XA = [0]
    Tag2_XA = [0]
    try:
    	Tag1_XA.extend(al1.get_tag("XA").split(";"))
	Tag1_XA = Tag1_XA[:-1]
    except:
	pass
    try:
    	Tag2_XA.extend(al2.get_tag("XA").split(";"))
	Tag2_XA = Tag2_XA[:-1]
    except:
	pass


    for k1, XA_al1 in enumerate(Tag1_XA):

	# if secondary
	if k1 > 0:
 		[al1_reference_name, al1_reference_start, al1_reference_end, al1_is_unmapped, al1_mapping_quality, al1_is_reverse, Al_S_1, al1_infer_query_length] = calcXAstats(XA_al1)
		#print al1
		#print al1_reference_name, al1_reference_start, al1_reference_end, al1_is_unmapped, al1_mapping_quality, al1_is_reverse, Al_S_1, al1_infer_query_length, "\n"
	else:
		[al1_reference_name, al1_reference_start, al1_reference_end, al1_is_unmapped, al1_mapping_quality, al1_is_reverse, Al_S_1, al1_infer_query_length] = [al1.reference_name, al1.reference_start, al1.reference_end, al1.is_unmapped, al1.mapping_quality, al1.is_reverse, float(al1.get_tag("AS")), al1.infer_query_length()]
		
	for k2, XA_al2 in enumerate(Tag2_XA):

		if k2 > 0:
			[al2_reference_name, al2_reference_start, al2_reference_end, al2_is_unmapped, al2_mapping_quality, al2_is_reverse, Al_S_2, al2_infer_query_length] = calcXAstats(XA_al2)
			#print al2
			#print al2_reference_name, al2_reference_start, al2_reference_end, al2_is_unmapped, al2_mapping_quality, al2_is_reverse, Al_S_2, al2_infer_query_length
		else:
			[al2_reference_name, al2_reference_start, al2_reference_end, al2_is_unmapped, al2_mapping_quality, al2_is_reverse, Al_S_2, al2_infer_query_length] = [al2.reference_name, al2.reference_start, al2.reference_end, al2.is_unmapped, al2.mapping_quality, al2.is_reverse, float(al2.get_tag("AS")), al2.infer_query_length()]
	
                counter+= 1
                al1_match = 0
		al2_match = 0
		map_type = 3 # improper value
                al1_reverse = 2 # improper value
                al2_reverse = 2 # improper value
                CLType = "22" 
                indivPos = -1 # temp position variable for map-type 1 clusters
                lf_bound = -1
                rt_bound = -1
                l_orient = 2
                r_orient = 2
                indivOrient = 2 
		lf_target = -1
		rt_target = -1
		left_tid = -1
		right_tid = -1
		Cl_small = -1
	
		if counter > PERMUTATION_THRESH:
			DList1 = []
			DList2 = []
			return

		
		if counter == 1:
                    ASF1 = Al_S_1
		    ASF2 = Al_S_2
		    Al_S_1 = BIG_NUM
		    Al_S_2 = BIG_NUM
		    

		if al1_reference_start == None and al1_reference_end == None and al2_reference_start == None and al2_reference_end == None:
			print "No pos continue"
			continue

		
                if ASF1 > AS_THRESH*al1_infer_query_length and Al_S_1 >= PCT_THRESH*ASF1:
			al1_match = 1

                if ASF2 > AS_THRESH*al2_infer_query_length and Al_S_2 >= PCT_THRESH*ASF2:
                    	al2_match = 1

		if not al1_match and not al2_match:
			continue

                if not al1_is_unmapped and not al2_is_unmapped and al1_reference_start!= None and al1_reference_end != None and al1_reference_start > -1 and al2_reference_start!=None and al2_reference_end !=None and al2_reference_start > -1 and al1_match and al2_match:

		    # if primary alignment below mapping quality threshold, don't use fragment at all
		    if (al1_mapping_quality < MAP_THRESH or al2_mapping_quality < MAP_THRESH) and counter == 1:
			DList1 = []
			DList2 = []
			return
		
 		    if counter == 1 and isinstance(al1_mapping_quality, int) and isinstance(al2_mapping_quality, int):
			    map_qual = min(al1_mapping_quality, al2_mapping_quality)
		    else:
			    map_qual = -1
                    map_type = 0

                    # All right if TID different or orientation different. Won't make any difference in those situations.
                    if (al1_reference_start <= al2_reference_start):
			# account for split alignments having different outer insert length
                        #OUTER_D = abs(al1_reference_start - al2_reference_end) + 2*RDL - Al_S_1 - Al_S_2
			OUTER_D = abs(al1.reference_end - al2.reference_start) + al1_infer_query_length + al2_infer_query_length
                        left_tid = al1_reference_name
                        right_tid = al2_reference_name
                        l_orient = al1_is_reverse
                        r_orient = al2_is_reverse

                    else:
                        #OUTER_D = abs(al2_reference_start - al1_reference_end) + 2*RDL - Al_S_1 - Al_S_2
			OUTER_D = abs(al2.reference_end - al1.reference_start) + al1_infer_query_length + al2_infer_query_length
                        left_tid = al2_reference_name
                        right_tid = al1_reference_name
                        l_orient = al2_is_reverse
                        r_orient = al1_is_reverse

                elif ((al1_reference_start== None and al1_reference_end == None) or al1_reference_start <= -1 or al1_is_unmapped) and (al2_reference_start!=None and al2_reference_end!=None and al2_reference_start > -1 and al2_reference_end > -1 and al2_match and not al2_is_unmapped):

		    if al2_mapping_quality < MAP_THRESH and counter == 1:
			DList1 = []
			DList2 = []
			return

		    if counter == 1 and isinstance(al2_mapping_quality, int):
			map_qual = al2_mapping_quality
		    else:
                            map_qual = -1

                    map_type = 1
                    
                    # left tid set by convention for one mate mappings
	            left_tid = al2_reference_name

                    if al2_is_reverse:
 
                        indivPos = al2_reference_start
                        indivOrient = 1
                        OUTER_D = -1

                    else:

                        indivPos = al2_reference_end
                        indivOrient = 0
                        OUTER_D = -1


                elif ((al2_reference_start== None and al2_reference_end == None) or al2_reference_start <= -1 or al2_is_unmapped) and (al1_reference_start!=None and al1_reference_end != None and al1_reference_start > -1 and al1_match and not al1_is_unmapped):

		    #print "Al 2 unmapped:", al2_is_unmapped
		    if al1_mapping_quality < MAP_THRESH and counter == 1:
			DList1 = []
			DList2 = []
			return
		   
   		    if counter == 1 and isinstance(al1_mapping_quality, int):
                        map_qual = al1_mapping_quality
		    else:
                            map_qual = -1
                    map_type = 1

		    left_tid = al1_reference_name	
	
                    if al1_is_reverse:
 
                        indivPos = al1_reference_start
                        indivOrient = 1
                        OUTER_D = -1

                    else:

                        indivPos = al1_reference_end
                        indivOrient = 0
                        OUTER_D = -1

		else:
			continue

     		if (len(str(left_tid)) > 1 and str(left_tid)[0:2] == "GL") or ((len(str(right_tid)) > 1 and str(right_tid)[0:2] == "GL")) or left_tid in ignoreTIDList or right_tid in ignoreTIDList:
			continue
 
		CLType = str(int(l_orient)) + str(int(r_orient))

                # If discordant (due to mapping distance or orientation or mapping TID)
                # Check just to be safe even though discordant flag set in creating BAM files
		#DISC_D=0
                if map_type == 1 or (map_type == 0 and abs(OUTER_D - MEAN_D) > DISC_dist) or (map_type==0 and CLType!="01") or (map_type == 0 and left_tid != right_tid):
			#print "Marked disc", al1, al2
                        temp=Cluster()
                	temp.mapqual = map_qual
			temp.ascore1 = Al_S_1
			temp.ascore2 = Al_S_2
			# "small" means discordant due to IL being smaller than threshold	
			if left_tid == right_tid and OUTER_D - MEAN_D < -1*DISC_dist:
				Cl_small = 1

                        if map_type == 0:
                           
			    # "Left" TID by convention is the one with the lower mapped coordinate if TIDs are different
                            if (al1_reference_start <= al2_reference_start) and (not al1_is_reverse) and (not al2_is_reverse):
                        
                                lf_bound = al1_reference_end                
                                rt_bound = al2_reference_end
      
                            elif (al1_reference_start <= al2_reference_start) and (not al1_is_reverse) and (al2_is_reverse):

                                lf_bound = al1_reference_end                
                                rt_bound = al2_reference_start
              			
                            elif (al1_reference_start <= al2_reference_start) and (al1_is_reverse) and (not al2_is_reverse):

                                lf_bound = al1_reference_start               
                                rt_bound = al2_reference_end
     
                            elif (al1_reference_start <= al2_reference_start) and (al1_is_reverse) and (al2_is_reverse):

                                lf_bound = al1_reference_start                
                                rt_bound = al2_reference_start
             			
                            elif (al1_reference_start > al2_reference_start) and (not al1_is_reverse) and (not al2_is_reverse):
                                
                                lf_bound = al2_reference_end              
                                rt_bound = al1_reference_end

                            elif (al1_reference_start > al2_reference_start) and (not al1_is_reverse) and (al2_is_reverse):

                                lf_bound = al2_reference_start               
                                rt_bound = al1_reference_end
         			
                            elif (al1_reference_start > al2_reference_start) and (al1_is_reverse) and (not al2_is_reverse):

                                lf_bound = al2_reference_end                
                                rt_bound = al1_reference_start
                                
                            elif (al1_reference_start > al2_reference_start) and (al1_is_reverse) and (al2_is_reverse):

                                lf_bound = al2_reference_start                
                                rt_bound = al1_reference_start
            				
                            temp.l_bound = lf_bound
                            temp.r_bound = rt_bound
                            temp.l_bound_O = lf_bound
                            temp.r_bound_O = rt_bound
                            temp.ltid = left_tid
                            temp.rtid = right_tid
			    temp.clsmall = Cl_small							
		
                        if map_type == 1:
			    temp.l_bound = indivPos
			    temp.r_bound = -1
                            temp.ltid = left_tid
			    CLType=  str(int(indivOrient)) + "2"
			    	
 			if ignoreR_FILE != "none" and ignoreRead(temp.ltid, temp.l_bound, temp.rtid, temp.r_bound):
				
				if counter == 1:
					DList1 = []
					DList2 = []
					return
				continue
			                           
                        temp.C_type = CLType
                        temp.Cmap_type = map_type

                        if temp.l_bound == None and temp.r_bound == None and temp.indiv_pos == None:
                            print "WARNING STORING BAD DATA ", temp


                        if map_type==0:
                            	
				DList1.append(temp)
 
                        if map_type == 1:
                            DList2.append(temp)

                # If even 1 alignment is concordant, don't use any mappings from read
                # Being recode-safe, as discordant flag is anyway set when creating the input BAM files
                else:

		    DList1 =[]
		    DList2 = []	
                    return
			       
    
def ReadNextReadAlignments(bamname):

    bamfile = pysam.AlignmentFile(bamname)

    for alignment in bamfile:
	if not alignment.is_secondary:
            yield alignment.qname, alignment                        
    
if __name__ == "__main__":

    f1 = open("../results/text/All_Discords_P.txt","w")
    f2 = open("../results/text/All_Discords_I.txt","w")
   
    print "Ignoring:", ignoreChr, ignoreR_FILE
 
    if ignoreChr != "none":
	recordChr()
 	print "Chromosomes", ignoreTIDList, "will be ignored."

    if ignoreR_FILE != "none":
        print "Forming hash table for bad regions..."
        formHash()
	print "Done."

    currentFrag = 1

    # Read discordant alignments and write all possible discordant pairs to file. 

    #fp = open("../results/text/DiscordFxnTimeLog.txt","w")
    
    print "Entering read loop..."

    start_for = time.clock()
    
    for (q1,aln1),(q2,aln2) in izip(ReadNextReadAlignments(FILE1),ReadNextReadAlignments(FILE2)):

	if (currentFrag % 100000) == 0:
		print "Fragment", currentFrag, "analyzed."

        assert q1[:-2] == q2[:-2]

        DList1 = []
        DList2 = []
        
        start_fd = time.clock()
        FormDiscordant(aln1, aln2, DList1, DList2)

        for item in DList1:
             f1.write("%s %s\n" %(currentFrag, item))
        for item in DList2:
             f2.write("%s %s\n" %(currentFrag, item))
        

        end_fd = time.clock()
    
        currentFrag = currentFrag + 1

        #fp.write("Loop %d %f\n" %(currentFrag,(end_fd-start_fd)))   

    end_for = time.clock()

    print "Done with loop"

    f1.close()
    f2.close()
    #fp.close()

    #f=open("../results/text/TimeLog.txt","w")
    #f.write("For loop time: %f, form-discordant fxn time: %f\n" %(end_for-start_for,end_fd-start_fd))
    #f.close()