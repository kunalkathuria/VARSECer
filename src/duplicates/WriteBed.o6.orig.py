# Can include check to see if map type = 1 if other documented end of random insertion was claimed or not. If not, belongs to another variant.
# Use formatBP.py to make bedpe documentation amenable to this reading format

import sys
import pysam
from collections import Counter
BAM = sys.argv[2]
DEL_THRESH = float(sys.argv[3])
DUP_THRESH = float(sys.argv[4])
DEL_THRESH2 = float(sys.argv[5])
DUP_THRESH2 = float(sys.argv[6])
PILEUP_THRESH = float(sys.argv[7])
MIN_PILEUP_THRESH = float(sys.argv[8])
RPT_REGIONS_FILE =  sys.argv[9]
GOOD_REG_THRESH=.55 # to trust pile-up depth in given region, this percentage should return data
GOOD_REG_THRESH2=.8 #to decide if SR DEL calls are true or not
SECOND_SWEEP_THRESH=.75
MINPU_MULT=2
chrHash = {}

class Variant(object):

    #$ add inv, ins also (bp 3)
    def __init__(self):
        self.bp = -1

        self.tid = -1

    def __str__(self):

        return "%s %s" %(self.bp, self.tid)

    def __hash__(self):
        return hash((self.bp, self.tid))

    def __eq__(self, other):
        return (self.bp, self.tid) == (other.bp, other.tid)

    def __ne__(self, other):
        # Not strictly necessary, but to avoid having both x==y and x!=y
        # True at the same time
        return not(self == other)

def formHash():

	print "Forming pile-up hash table..."
        fo=open(RPT_REGIONS_FILE,"r")
	prev_start = -1
	prev_stop = -1

        for k,line in enumerate(fo):
                line_s = line.split()
                currentTID = line_s[0]
		start = int(line_s[1])
		stop = int(line_s[2])+1

		# make hash table of unreliable regions if greater than RDL (almt would be doubtful there)
		if prev_stop != -1 and currentTID == prevTID and start - prev_stop > RDL:
	
	                for x in range(prev_stop, start):
				temp = Variant()
				temp.tid = currentTID
				temp.bp = x
				if temp not in chrHash:
	                	        chrHash[temp] = 1

		prev_start = start
		prev_stop = stop
		prevTID = currentTID

	print "Done"

def file_len(f):
    
    for i, l in enumerate(f):
        pass
    return i + 1

if __name__ == "__main__":

	f1 = open("../results/text/All_Variants.txt","r")
        f8 = open(sys.argv[1],"r")
	f11 = open("../results/text/allPositives.txt","w")
	f12 = open("../results/text/allPositives.bedpe","w")
	f13 = open("../results/text/deletions.bedpe","w")
	f13b = open("../results/text/deletions_01.bedpe","w")
        f14 = open("../results/text/tandemDuplications.bedpe","w")
        f15 = open("../results/text/inversions.bedpe","w")
        f16 = open("../results/text/insertions.bedpe","w")
        f17 = open("../results/text/unknowns.bedpe","w")

	fo = open("../results/text/bam_stats.txt","r")		
	RDL = -1
	SD = -1
	for i,line in enumerate(fo):
		if i == 0:
			RDL=float(line[:-1])
		elif i==2:
			SD=float(line[:-1])
		elif i==3:
			break
	COVERAGE = float(line[:-1])
	print "Coverage is:", COVERAGE
	SR_DEL_THRESH=100
	PE_DEL_THRESH_S=250
	PE_DEL_THRESH_L=100
	SD_S = 15
	SD_L = 50
	# calculate min PE size based on insert length standard deviation under simple empirical linear model, and nature of small calls that fits generally well
	PE_DEL_THRESH=PE_DEL_THRESH_S + int((SD-SD_S)*(PE_DEL_THRESH_L-PE_DEL_THRESH_S)/(SD_L-SD_S))

	DisjSC = []

        for line in f8:
				
                DisjSC.append(int(line))
		
        y = Counter(DisjSC)
	counter = -1
	samfile = pysam.AlignmentFile(BAM, "rb" )
	if RPT_REGIONS_FILE != "none":
		formHash()

	for line2 in f1:
		counter+=1
		if counter % 100 == 0:
			print "Writing Variant", counter
		line2_split = line2.split()
		num = int(line2_split[0])

		if y[num] > 0:
                   
			if line2_split[11].find("RD") == -1: 
				#print num
				#f11.write("%s\n" %line2)
				swap = 0
				GT=""
				if (line2_split[1] == "DEL_INS" or line2_split[1] == "DEL" or line2_split[1][0:2]== "TD") and int(line2_split[4]) + MINPU_MULT*MIN_PILEUP_THRESH < int(line2_split[6]):
					chr_n = line2_split[2]
					gap = int(line2_split[6])-int(line2_split[4])
					start = .25*gap + int(line2_split[4])
					stop = min(start+.5*gap,start +3*PILEUP_THRESH)
					covLoc = 0
					counter2 = 0
					
					for pileupcolumn in samfile.pileup(chr_n, start, stop):
						temp = Variant()
						temp.tid, temp.bp = chr_n, pileupcolumn.pos
						
						if temp not in chrHash:
							#print "DEL hash", pileupcolumn.pos, pileupcolumn.n
							covLoc = covLoc + pileupcolumn.n
							counter2+=1
							if counter2 > PILEUP_THRESH:
								break

					#print 1.0*covLoc/(.001+counter2), "is local coverage", counter2, counter3, covLoc

					if counter2 > MIN_PILEUP_THRESH and (counter2 > GOOD_REG_THRESH*(stop-start) or counter2 > PILEUP_THRESH):
	
						covLoc = (1.0*covLoc)/(1.0*counter2)
						#print covLoc, "is local coverage", counter2, counter3
	
						if line2_split[1][0:2] == "TD" and covLoc/COVERAGE > DUP_THRESH:
						
							print "TD confirmed (pileup)"	
							line2_split[1] = "TD"
							#if covLoc/COVERAGE > DUP_THRESH2:
								#GT="GT:1/1"
						
						elif line2_split[1][0:2] == "TD" and covLoc/COVERAGE < 1.0:
					
							line2_split[1] = "BND"
				
						elif line2_split[1][0:3] == "DEL" and covLoc/COVERAGE < DEL_THRESH and counter2 > GOOD_REG_THRESH2*(stop-start):
						
							print "DEL confirmed (pileup)"
							line2_split[1] = "DEL"
							if covLoc/COVERAGE < DEL_THRESH2:
								GT="GT:1/1"
							elif covLoc/COVERAGE > 3*DEL_THRESH2:	
								GT="GT:0/1"

						elif line2_split[1][0:3] == "DEL" and covLoc/COVERAGE > DUP_THRESH:

							# since bp3 = -1, this will be written as a BND event
							line2_split[1] = "INS"
					
				# can add this and regular TDs also
				elif len(line2_split[1]) > 2 and (line2_split[1][0:3] == "INS" or line2_split[1] == "INS_I") and int(line2_split[7]) + MINPU_MULT*MIN_PILEUP_THRESH < int(line2_split[9]):

					chr_n = line2_split[5]
					gap = int(line2_split[9])-int(line2_split[7])
                                        start = .25*gap + int(line2_split[7])
                                        stop = min(start+.5*gap,start +3*PILEUP_THRESH)
                                        covLoc = 0
                                        counter2 = 0

                                        for pileupcolumn in samfile.pileup(chr_n, start, stop):
                                                        covLoc = covLoc + pileupcolumn.n
                                                        counter2+=1
                                                        if counter2 > PILEUP_THRESH:
                                                                break

					if counter2 > MIN_PILEUP_THRESH and (counter2 > GOOD_REG_THRESH*(stop-start) or counter2 > PILEUP_THRESH):

						covLoc = (1.0*covLoc)/(1.0*counter2)

						if covLoc/COVERAGE < DEL_THRESH:
							line2_split[1] = "INS_C_P"
						elif covLoc/COVERAGE < 1.1:
							line2_split[1] = "INS_C"

				elif len(line2_split[1]) > 4 and line2_split[1][0:4] == "INS_C":

					chr_n = line2_split[5]
					start1 = int(line2_split[4])
					stop1 = int(line2_split[6])
					start2 = int(line2_split[7])
					stop2 = int(line2_split[9])
					if start1 > stop2:

						start1 = int(line2_split[10])
						stop2 = int(line2_split[3])

					if start1 < start2 < stop2:

						covLoc = 0
                                                counter2 = 0
						x = start1
                                        	for pileupcolumn in samfile.pileup(chr_n, start1, stop1):
							covLoc = covLoc + pileupcolumn.n
							counter2+=1
							if counter2 > PILEUP_THRESH:
								break
                                                	x+=1
							if x-start > 5*PILEUP_THRESH:
                                                        	break
						covLoc = 1.0*(covLoc/counter2)

						covLoc2 = 0
						counter3 = 0
						x = start2
                                                for pileupcolumn in samfile.pileup(chr_n, start2, stop2):
							covLoc2 = covLoc2 + pileupcolumn.n
							counter3+=1
							if counter3 > PILEUP_THRESH:
								break
                                                        x+=1
							if x-start > 5*PILEUP_THRESH:
                                                        	break
						covLoc2 = 1.0*(covLoc2/counter3)

						# don't use pile up to sort v small variants
						if counter2 > MIN_PILEUP_THRESH and (counter2 > PILEUP_THRESH or counter2 > GOOD_REG_THRESH*(stop-start)):

						   if counter3 > MIN_PILEUP_THRESH and (counter3 > PILEUP_THRESH or counter3 > GOOD_REG_THRESH*(stop-start)):

							if covLoc/COVERAGE < DUP_THRESH and covLoc2/COVERAGE > 1.2*DUP_THRESH:
								line2_split[1] = "INS"
								#$ call another diploid deletion here

							elif covLoc2/COVERAGE < DEL_THRESH or covLoc/COVERAGE < DEL_THRESH:
								line2_split[1] = "BND_INS_C"

							elif (line2_split[1] == "INS_C" or line2_split[1] == "INS_C_I") and covLoc/COVERAGE > DUP_THRESH and covLoc2/COVERAGE < DUP_THRESH:
								swap = 1
								if covLoc/COVERAGE > 1.2*DUP_THRESH:
									line2_split[1] = "INS"
								#$ call another diploid deletion here
					else:
						line2_split[1] = "BND_INS_C"	

			if line2_split[1] == "DEL":
                           
			    if line2_split[11].find("SR") != -1 and int(line2_split[7]) - int(line2_split[3]) < SR_DEL_THRESH:
                                continue
                            elif line2_split[11].find("SR") == -1 and int(line2_split[7]) - int(line2_split[3]) < PE_DEL_THRESH:
                                continue
 
                            f13.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], line2_split[3], line2_split[4], line2_split[5], line2_split[6], line2_split[7],"DEL",GT))
                        #$Comment out second condition and next elif if leads to low precision due to SR TD_I's and INS_I's.    
                        elif line2_split[1] == "TD":

			    [bp1_s, bp1_e] = min(int(line2_split[3]),int(line2_split[6])), min(int(line2_split[4]), int(line2_split[7]))
			    [bp2_s, bp2_e] = max(int(line2_split[3]),int(line2_split[6])), max(int(line2_split[4]), int(line2_split[7]))
 
			    f14.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], bp1_s, bp1_e, line2_split[5], bp2_s, bp2_e,"TD",GT))

			#See whether this works better for PE only vs PE and SR both-- unlikely to have inv TD...
			elif line2_split[1] == "INS_I" and line2_split[2] == line2_split[5] and line2_split[8] == "-1" and line2_split[11][:2] == "PE":
			
			    [bp1_s, bp1_e] = min(int(line2_split[3]),int(line2_split[6])), min(int(line2_split[4]), int(line2_split[7]))
                            [bp2_s, bp2_e] = max(int(line2_split[3]),int(line2_split[6])), max(int(line2_split[4]), int(line2_split[7]))

                            f14.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], bp1_s, bp1_e, line2_split[5], bp2_s, bp2_e,"TD_INV",GT))

			elif line2_split[1] == "INV":
                            f15.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], line2_split[3], line2_split[4], line2_split[5], line2_split[6], line2_split[7],line2_split[1],GT))

			# this is read from cluster file, so has 2 bps only; INS_C w/ only 2 clusters supporting; INV w/ only 1
                        elif line2_split[1] == "Unknown" or line2_split[1] == "INS_POSS" or line2_split[1] == "TD_I" or line2_split[1] == "INV_POSS" or ( (line2_split[1] == "INS" or line2_split[1] == "INS_I" or line2_split[1] == "INS_C" or line2_split[1] == "INS_C_I") and (line2_split[9] == "-1" or line2_split[6] == "-1")) or (line2_split[1] == "INS_C" and line2_split[12] == "2"):

                            f17.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], line2_split[3], line2_split[4], line2_split[5], line2_split[6], line2_split[7],"BND", line2_split[1],GT))

                        elif len(line2_split[1]) > 2 and line2_split[1][0:3] == "INS":

			    # two lines for insertion as in bedpe format; bp 1 and bp3 were flanks of bp2 by convention in INS_C classification unless confirmed further
			    [bp1_s, bp1_e]= int(line2_split[3]), int(line2_split[4])
			    [bp2_s, bp2_e] = int(line2_split[6]),int(line2_split[7])
                            [bp3_s, bp3_e] = int(line2_split[9]),int(line2_split[10])
			    
			    if swap:
				temp = bp1_e
				bp1_e = bp3_e
				bp3_e = temp
				bp1_s = bp3_s
				
			    if not (line2_split[1] == "INS_C" or line2_split[1] == "INS_C_I") and bp2_s > bp3_e and not swap:
				temp = bp2_s
				bp2_s = bp3_e
				bp3_e = temp 

			    # it was INS_C
			    elif bp2_s > bp3_e:

				bp2_s = bp3_s
				bp3_e = bp2_e
						
                            f16.write("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" %(line2_split[5], bp2_s, bp3_e, line2_split[2], bp1_s, bp1_e, line2_split[1],GT))

                        else:
				f17.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], line2_split[3], line2_split[4], line2_split[5], line2_split[6], line2_split[7],"BND", line2_split[1],GT))
 
	    	if line2_split[1] == "DEL_uc":

                            f13b.write(("%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n") %(line2_split[2], line2_split[3], line2_split[4], line2_split[5], line2_split[6], line2_split[7],line2_split[1],GT))
	
	f1.close()
	f8.close()
        f11.close()
	f12.close()
	f13.close()
	f14.close()
	f15.close()
	f16.close()
	f17.close()
	samfile.close()



                                        
                        