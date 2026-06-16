# Comprehensive red blood cell and platelet antigen prediction from whole genome sequencing: proof of principle

## Abstract

BACKGROUND There are 346 serologically defined red blood cell (RBC) antigens and 33 serologically defined platelet (PLT) antigens, most of which have known genetic changes in 45 RBC or six PLT genes that correlate with antigen expression. Polymorphic sites associated with antigen expression in the primary literature and reference databases are annotated according to nucleotide positions in cDNA. This makes antigen prediction from next‐generation sequencing data challenging, since it uses genomic coordinates. STUDY DESIGN AND METHODS The conventional cDNA reference sequences for all known RBC and PLT genes that correlate with antigen expression were aligned to the human reference genome. The alignments allowed conversion of conventional cDNA nucleotide positions to the corresponding genomic coordinates. RBC and PLT antigen prediction was then performed using the human reference genome and whole genome sequencing (WGS) data with serologic confirmation. RESULTS Some major differences and alignment issues were found when attempting to convert the conventional cDNA to human reference genome sequences for the following genes: ABO , A4GALT , RHD , RHCE , FUT3 , ACKR1 (previously DARC ), ACHE , FUT2 , CR1 , GCNT2 , and RHAG . However, it was possible to create usable alignments, which facilitated the prediction of all RBC and PLT antigens with a known molecular basis from WGS data. Traditional serologic typing for 18 RBC antigens were in agreement with the WGS‐based antigen predictions, providing proof of principle for this approach. CONCLUSION Detailed mapping of conventional cDNA annotated RBC and PLT alleles can enable accurate prediction of RBC and PLT antigens from whole genomic sequencing data.

Prediction of red blood cell (RBC) and platelet (PLT) antigens using DNA assays has the potential to augment or replace traditional serologic antigen typing in many situations. DNA‐based typing methods are more easily automated, amenable to multiplexing, and do not require expensive and sometimes difficult to obtain serologic immunoglobulin reagents. As such, DNA‐based approaches could allow for more extensive characterization of patient and donor phenotypes and enable enhanced blood product selection and identification of donors with rare phenotypes.

There are 346 serologically distinct RBC blood group antigen phenotypes recognized by the International Society of Blood Transfusion (ISBT). 1 For most RBC antigens there is a known correlation between the antigen phenotype and one or more molecular changes defined by more than 1100 alleles across 45 genes. 2 , 3 , 4 , 5 , 6 , 7 , 8 , 9 There are 33 serologically distinct human PLT antigen (HPA) phenotypes recognized by the Platelet Nomenclature Committee. 10 For all 33 PLT antigens, the molecular basis is known and can be characterized by 33 alleles within six genes. 10 , 11 , 12 Resources that catalog RBC antigen allele variants include the ISBT website, 2 the Blood Group Antigen FactsBook, 3 the BGMUT website, 13 and the RHD RhesusBase. 14 Alleles encoding PLT antigens are available from the Immuno Polymorphism Database‐HPA website. 10 , 11 , 12 These resources provide a means to validate and design single‐nucleotide polymorphism (SNP) assays to predict phenotypes. However, current SNP‐based molecular typing assays have limitations 15 , 16 including: 1) need for specialized testing instruments, reagents, and workflows; 2) do not include all of the known blood group genes; 3) target selective gene regions without evaluating all potentially contributory genetic changes; and 4) more complex antigens require the integration of multiple assays. 16 

The RH (e.g., D, C/c, E/e) and MNS (e.g., M/N, S/s) blood group system antigens are challenging to predict given the large number of complex alleles, genetic variation, and gene rearrangements between RHD / RHCE and GYPA / GYPB / GYPE . Most of the other RBC protein antigens (e.g., K/k, Fy a/b ) are the result of single well‐characterized inherited missense variants. 3 , 4 However, additional molecular changes can cause antigen expression to be weak or silenced (null) due to alternative splicing, premature stop codons, hybrid genes, promoter silencing, and at the protein level, altered membrane insertion or changes to interacting proteins or modifying genes. High‐resolution predictive accuracy would require large regions of sequence coverage to identify all potentially relevant changes. Although commercial SNP assays evaluate common polymorphisms to predict protein‐based antigens, 15 , 17 they do not include all clinically significant changes.

The RBC carbohydrate antigens (e.g., ABO, Le a/b , P1, P k ) are synthesized by enzymes. 3 DNA‐based determination of carbohydrate antigen expression is not widespread because accurate prediction requires gene sequencing to properly predict the enzymatic and sugar specificity across several genes (e.g., ABO antigen prediction requires evaluation of ABO along with FUT1  3 , 19 and FUT2  21 , 22 ). In addition, alleles associated with carbohydrate antigens are complex, often contain multiple nucleotide changes, and are numerous (e.g., >300 ABO alleles reported 13 ), with many different null alleles. The clinical significance of missing one inactivating mutation for ABO is an unacceptable risk for transfusion and, therefore, the limited sequence coverage of SNP targeted typing is currently inadequate.

PLT antigens are mainly associated with single missense variants. 23 Although molecular assays exist to predict PLT antigens, 24 matching for patients, with the possible exception of HPA‐1a, is underutilized in clinical practice at the present time given the cost and lack of antigen typed donors.

Next‐generation sequencing (NGS) would overcome many of the limitations associated with SNP‐based assays. NGS‐based molecular prediction has been successfully applied to human leukocyte antigens 25 , 26 , 27 , 28 , 29 , 30 and human neutrophil antigens. 31 However, there are no published reports of NGS‐based PLT antigen prediction and only three reports of targeted NGS‐based RBC antigen prediction: 1) RHD in 26 samples with weak D antigens, 32 2) K/k allelic polymorphism (c.578) using cell‐free fetal DNA in three pregnant females, 33 and 3) 18 genes that control 15 blood group systems in four individuals. 34 Recently, an algorithm was published 35 that used the BGMUT database 13 to predict RBC antigens for ABO and D typed individuals from the personal genome. 36 , 37 

With the emergence of genomic approaches and personalized medicine, NGS‐based whole genome sequencing (WGS) data could be used to evaluate genes encoding RBC and PLT antigens to predict the presence of antigens with a known molecular basis. There are no reports describing comprehensive WGS‐based RBC or PLT antigen prediction. One of the challenges for this approach is that the allele reference sources list the nucleotide changes according to coding DNA sequence (CDS) positions based on cDNA sequences. It is not readily possible to predict RBC and PLT antigens from WGS data, since the data use genomic coordinates linked to the human reference genome. In this article we describe an approach for the prediction of RBC and PLT antigens from WGS data and demonstrate the feasibility of the approach.


## MATERIALS AND METHODS


### Conversion of conventional cDNA positions to genomic coordinates

Conventional cDNA reference sequence CDS positions were converted to genomic coordinates: 1) reference cDNA and protein sequences were downloaded from GenBank; 2) human reference genome UCSC genomic transcripts, corresponding to the splicing pattern of the conventional cDNA sequence, were downloaded in a format identifying the exons and introns and the genomic start and end positions (exons, uppercase; introns, lowercase); 3) the cDNA reference sequence and the human reference genome sequences were aligned using Clustal Omega v1.1.1; 38 4) the start and termination codon genomic positions were manually determined in the Integrated Genomic Viewer Version 2.3.26; 39 and 5) the CDS start position and alignments were then used as a reference to convert between cDNA, gene, and genomic coordinate positions.

Conventional cDNA reference sequence CDS positions were converted to genomic coordinates: 1) reference cDNA and protein sequences were downloaded from GenBank; 2) human reference genome UCSC genomic transcripts, corresponding to the splicing pattern of the conventional cDNA sequence, were downloaded in a format identifying the exons and introns and the genomic start and end positions (exons, uppercase; introns, lowercase); 3) the cDNA reference sequence and the human reference genome sequences were aligned using Clustal Omega v1.1.1; 38 4) the start and termination codon genomic positions were manually determined in the Integrated Genomic Viewer Version 2.3.26; 39 and 5) the CDS start position and alignments were then used as a reference to convert between cDNA, gene, and genomic coordinate positions.


### Predicting antigens from the human reference genome

RBC and PLT antigens encoded by each cDNA reference sequence are well established. 2 , 3 , 10 The conventional cDNA reference and human reference genome alignments were used to determine the CDS and amino acid positions that differed. The known alleles 2 , 3 , 4 , 10 , 12 , 23 were used to manually determine if any difference altered the presence or absence of a RBC and PLT antigen, which allowed for the prediction of the RBC and PLT antigens encoded by the human reference genome.

RBC and PLT antigens encoded by each cDNA reference sequence are well established. 2 , 3 , 10 The conventional cDNA reference and human reference genome alignments were used to determine the CDS and amino acid positions that differed. The known alleles 2 , 3 , 4 , 10 , 12 , 23 were used to manually determine if any difference altered the presence or absence of a RBC and PLT antigen, which allowed for the prediction of the RBC and PLT antigens encoded by the human reference genome.


### WGS‐based antigen prediction

With approval from the Partners HealthCare Human Research Committee, a sample for RBC phenotyping and genomic DNA isolation was collected from a patient participating in the MedSeq Project. 40 Whole genomic sequencing was performed by the CLIA‐certified, CAP‐accredited Illumina Clinical Services Laboratory (San Diego, CA) using paired‐end 100‐bp reads on the Illumina HiSeq platform and sequenced to at least 30× mean coverage. 41 The genomic data from the MedSeq project has being submitted to the dbGaP website. The genome used in this article is from dbGaP subject ID 1270611. Sequence read data were aligned to the human reference sequence (GRCh37/hg19) using Burrows‐Wheeler Aligner 0.6.1‐r104. 42 Variant calls for 45 RBC and six HPA genes (300 bases upstream of start codon, exons, and 10 bases into each intron) were made using the Genomic Analysis Tool Kit Version 2.3‐9‐gdcdccbb and saved as a variant calling format (.vcf) file showing differences between the WGS data and the reference genome. 43 Sequencing coverage was extracted from the alignment file using BEDTools v2.17.0. 44 The Integrative Genomics Viewer 39 was used to verify coverage and sequence identity for positions in the .vcf file.

The genomic coordinates from the .vcf file were converted into CDS positions relative to the conventional cDNA sequences. Each variant was then compared to published allele tables. 2 , 3 , 4 , 10 , 12 , 23 For alleles with nucleotide changes in the 3′, 5′, and intronic regions, the genomic coordinates were manually determined and evaluated in the NGS alignment file for the presence or absence of the antigen from published allele tables. 2 , 3 , 4 , 10 , 12 , 23 To predict antigens with positions not in the .vcf file, the sequence coverage was analyzed for adequacy and if adequate the human reference genome prediction was used.

With approval from the Partners HealthCare Human Research Committee, a sample for RBC phenotyping and genomic DNA isolation was collected from a patient participating in the MedSeq Project. 40 Whole genomic sequencing was performed by the CLIA‐certified, CAP‐accredited Illumina Clinical Services Laboratory (San Diego, CA) using paired‐end 100‐bp reads on the Illumina HiSeq platform and sequenced to at least 30× mean coverage. 41 The genomic data from the MedSeq project has being submitted to the dbGaP website. The genome used in this article is from dbGaP subject ID 1270611. Sequence read data were aligned to the human reference sequence (GRCh37/hg19) using Burrows‐Wheeler Aligner 0.6.1‐r104. 42 Variant calls for 45 RBC and six HPA genes (300 bases upstream of start codon, exons, and 10 bases into each intron) were made using the Genomic Analysis Tool Kit Version 2.3‐9‐gdcdccbb and saved as a variant calling format (.vcf) file showing differences between the WGS data and the reference genome. 43 Sequencing coverage was extracted from the alignment file using BEDTools v2.17.0. 44 The Integrative Genomics Viewer 39 was used to verify coverage and sequence identity for positions in the .vcf file.

The genomic coordinates from the .vcf file were converted into CDS positions relative to the conventional cDNA sequences. Each variant was then compared to published allele tables. 2 , 3 , 4 , 10 , 12 , 23 For alleles with nucleotide changes in the 3′, 5′, and intronic regions, the genomic coordinates were manually determined and evaluated in the NGS alignment file for the presence or absence of the antigen from published allele tables. 2 , 3 , 4 , 10 , 12 , 23 To predict antigens with positions not in the .vcf file, the sequence coverage was analyzed for adequacy and if adequate the human reference genome prediction was used.


### RBC serology

RBC serologic antigen typing by tube method was performed according to standard blood banking practices in the Brigham and Women's Hospital Blood Bank. Commercially available serologic typing reagents were used to type for the ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s antigens.

RBC serologic antigen typing by tube method was performed according to standard blood banking practices in the Brigham and Women's Hospital Blood Bank. Commercially available serologic typing reagents were used to type for the ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s antigens.


## RESULTS


### Conversion of cDNA positions to genomic coordinates

RBC and PLT antigen polymorphisms have historically been defined using CDS positions referenced to published cDNA sequences with the A of the start codon (ATG) as Position 1. To predict antigens from NGS data, a manual workflow was created to map the CDS nucleotide changes to the respective genomic coordinates using alignments between the cDNA reference sequence and the GRCh37/hg19 human reference genome sequence for the cDNA, CDS, and protein sequences. Figure 1 and Table 1 illustrate the process for the Duffy system. The Fy a /Fy b antigens, c.125G/A, map to chr1:159,175,354G/A, and genomic coordinates were also determined for other reported FY alleles.

RBC and PLT antigen polymorphisms have historically been defined using CDS positions referenced to published cDNA sequences with the A of the start codon (ATG) as Position 1. To predict antigens from NGS data, a manual workflow was created to map the CDS nucleotide changes to the respective genomic coordinates using alignments between the cDNA reference sequence and the GRCh37/hg19 human reference genome sequence for the cDNA, CDS, and protein sequences. Figure 1 and Table 1 illustrate the process for the Duffy system. The Fy a /Fy b antigens, c.125G/A, map to chr1:159,175,354G/A, and genomic coordinates were also determined for other reported FY alleles.


*Approach for mapping conventional cDNA reference sequence positions to genomic coordinates. (A) Process developed to convert conventional CDS positions to genomic coordinates with FY as an example. (B) CDS positions referenced to cDNA sequence. (C and D) Genome transcript and genomic coordinates according to the human reference genome. (E) UCSC genomic sequence in which each exon and intron is annotated as separate sequence entry preceded by the genomic coordinates. The sequence regions are colored: 3′ and 5′ (gray), CDS (green uppercase), and intron (blue lowercase). (F) FY gene conversion between genomic coordinates and cDNA reference sequence.*


*FY alleles, cDNA and genomic coordinates, bases(s) found, WGS coverage, and result*


**Allele** | **CDS** | **Gene** | **Genome** | **Base(s) found** | **Coverage** | **Result**
 FY*01N.01  | c.−67 | g.881 | chr1:159,174,683 | T | 28× | Absent
 FY*01/02  | c.125 | g.1552 | chr1:159,175,354 | G/A | 15/15× | Fy(a+b+)
 FY*02M.02  | c.145 | g.1572 | chr1:159,175,374 | G | 24× | Absent
 FY*02M.01/02  | c.265 | g.1692 | chr1:159,175,494 | C | 27× | Absent
 FY*01N.02  | c.281_295 | g.1708_1722 | chr1:159,175,510_chr1:159,175,524 | CTGGCT GGCCTGTCC | 31‐36× | Absent
 FY*01N.04  | c.287 | g.1714 | chr1:159,175,516 | G | 34× | Absent
 FY*02M.01/02  | c.298 | g.1725 | chr1:159,175,527 | G | 32× | Absent
 FY*01N.05  | c.327 | g.1754 | chr1:159,175,556 | C | 37× | Absent
 FY*02N.02  | c.407 | g.1834 | chr1:159,175,636 | G | 27× | Absent
 FY*01N.03  | c.408 | g.1835 | chr1:159,175,637 | G | 28× | Absent


### Differences between conventional cDNA and human reference genome

From the conversion and alignment process, differences were observed between conventional cDNA and the human reference genome. Minor differences included: 1) silent variants that do not encode amino acid changes, 2) different antigen allele, and 3) potentially nonrelevant missense changes. Table 2 summarizes the blood group, gene, nucleotide, and amino acid differences; location of change; or predicted impact on antigen expression. Major differences that would challenge interpretation were encountered in the following genes: ABO , A4GALT , RHD , RHCE , FUT3 , ACKRI (previously DARC ), ACHE , FUT2 , CR1 , GCNT2 , and RHAG , summarized in Table 2 .

From the conversion and alignment process, differences were observed between conventional cDNA and the human reference genome. Minor differences included: 1) silent variants that do not encode amino acid changes, 2) different antigen allele, and 3) potentially nonrelevant missense changes. Table 2 summarizes the blood group, gene, nucleotide, and amino acid differences; location of change; or predicted impact on antigen expression. Major differences that would challenge interpretation were encountered in the following genes: ABO , A4GALT , RHD , RHCE , FUT3 , ACKRI (previously DARC ), ACHE , FUT2 , CR1 , GCNT2 , and RHAG , summarized in Table 2 .


*Differences encountered when aligning the conventional cDNA with the human reference genome (shown as conventional reference > reference genome)*


**Symbol** | **Gene** | **CDS nucleotide (genomic coordinate) [amino acid]** | **Differences**
ABO |  ABO  | c.261delG (no genomic coordinate) | Genome: inactive enzyme Exons 1‐5 correspond to ABO.O.01.02 Exons 6 and 7 correspond to ABO*O.01.01 
MNS |  GYPA  | c.38(chr4:145,041,741)C>A [p.Ala13Glu]; c.59(chr4:145,041,720)C>T [p.Ser20Lue], c.71(chr4:145,041,708)G>A, c.72(chr4:145,041,707)T>G [p.Gly24Glu]; c.93(chr4:145,041,686)C>T [p.Thr31Thr] | Probable nonrelevant missense change in cleaved N‐term; Antigenic difference: M+N−>M−N+; Silent change
MNS |  GYPB  | c.251(chr4:144,918,712)C>G [p.Thr84Ser] | Presumed non‐relevant missense change c.251G is part of the S−s−U+w [GYPB.NY] allele which has additional changes c.208G>T and c.230C>T not present in the reference genome
P1PK |  A4GALT  |  | Two different cDNA reference sequences
RH |  RHD  | c.1136(chr1:25,643,553)C>T [p.Thr379Met] | Genome: common African black allele
RH |  RHCE  | c.48(chr1:25,747,230)G>C [p.Trp16Cys] | Genome: common African black allele
LU |  BCAM  ( LU ) | c.1615(chr19:45,322,744)G>A [p.Ala539Thr] | Antigenic difference: Au(a−b+) > Au(a+b−)
LE |  FUT3  | c.202(chr19:5,844,649)T>C [p.Trp68Arg], c.314(chr19:5,844,537)C>T [p.Thr105tMet] | Genome: inactive enzyme associated with a Le(a−b−) phenotype
FY |  ACKR1  ( DARC ) |  | Conventional: reference is alternative splice form with different numbering than the alleles
DI |  SLC4A1  | c.357(chr17:42,337,900)T>C [p.Val119Val] | Silent change
YT |  ACHE  |  | Conventional reference is alternative splice form with different numbering and splice form was not deposited into GenBank
DO |  ART4  | c.378(chr12:14,993,854)C>T [p.Tyr126Tyr], c.624(chr12:14,993,608)T>C [p.Leu208Leu]; c.793(chr12:14,993,439)A>G [p.Asn265Asp] | Silent changes; Antigenic difference: Do(a+b−) > Do(a−b+)
H |  FUT2  |  | Conventional reference is numbered to alternative splice form rather than the deposited long isoform
KN |  CR1  | c.4828(chr1:207,782,916)T>A [p.Ser1610Thr] | Genome: rare Sl3– phenotype
IN |  CD44  | c.326(chr11:35,201,913)A>C [p.Tyr109Ser] | Found in association with rare In(a+b−) phenotype but with additional changes c.137G>C p.Arg46Pro and c.716G>A p.Gly239Glu. It is unclear if c.326A>C alone can lead to antigenic change.
OK |  BSG  | c.537(chr19:581,407)T>C [p.Asp179Asp] | Silent change
RAPH |  CD151  | c.579(chr11:837,582)A>G [p.Gly193Gly] | Silent change
I |  GCNT2  | c.816(chr6:10,587,038)G>C [p.Glu272Asp] | Genome: uncommon allele with unclear phenotype
GIL |  AQP3  | c.61(chr9:33,447,468)T>C [p.Leu21Leu], c.105(chr9:33,447,424)C>G [p.Leu35Leu], c.390(chr9:33,442,952)T>C [p.Phe130Phe], c.543(chr9:33,442,466)T>C [p.Pro181Pro] | Silent changes
RHAG |  RHAG  | c.724(chr6:49,582,483)G>A [p.Asn242Asp] | Conventional reference sequence sequencing error


#### ABO

The ABO gene determines the transferase enzymes responsible for the carbohydrate antigens, A and B. Any mutation that results in absence of transferase activity results in Group O. The conventional cDNA reference is an A allele. By analyzing the ABO gene region in the human reference genome it was found to represent sequence regions from two separate human reference genome sequencing contigs representing different haplotype alleles: 1) The AL158826.23 contig, which contains Exons 1 to 5 corresponds to the ABO.O.01.02 allele, and 2) the AL732364.9 contig, which contains Exons 6 to 7 matches the ABO*O.01.01 allele. 3 Therefore, the reference sequence contains a deletion characteristic of O 1 alleles (c.261delG) and when analyzing NGS data A and B allele sequences would appear to have an insertion (chr1:136132908_136132909insG) and O 1 alleles would not have the characteristic deletion.

The ABO gene determines the transferase enzymes responsible for the carbohydrate antigens, A and B. Any mutation that results in absence of transferase activity results in Group O. The conventional cDNA reference is an A allele. By analyzing the ABO gene region in the human reference genome it was found to represent sequence regions from two separate human reference genome sequencing contigs representing different haplotype alleles: 1) The AL158826.23 contig, which contains Exons 1 to 5 corresponds to the ABO.O.01.02 allele, and 2) the AL732364.9 contig, which contains Exons 6 to 7 matches the ABO*O.01.01 allele. 3 Therefore, the reference sequence contains a deletion characteristic of O 1 alleles (c.261delG) and when analyzing NGS data A and B allele sequences would appear to have an insertion (chr1:136132908_136132909insG) and O 1 alleles would not have the characteristic deletion.


#### A4GALT (P1PK)

The A4GALT gene encodes a lactosylceramide 4‐α‐galactosyltransferase enzyme responsible for the carbohydrate P1PK system antigens: P1 and P k . All of the known P1PK null alleles are referenced using the splice form I reference sequence ( GU902278 ‐ GU902281 ), but all of the nucleotides associated with P1+ and P1− expression are located in a skipped Exon 2a, which is only found in the alternative spliced form IV of A4GALT ( AJ245581 ). 45 Therefore, mapping required use of both conventional reference sequences to obtain the corresponding genomic coordinates.

The A4GALT gene encodes a lactosylceramide 4‐α‐galactosyltransferase enzyme responsible for the carbohydrate P1PK system antigens: P1 and P k . All of the known P1PK null alleles are referenced using the splice form I reference sequence ( GU902278 ‐ GU902281 ), but all of the nucleotides associated with P1+ and P1− expression are located in a skipped Exon 2a, which is only found in the alternative spliced form IV of A4GALT ( AJ245581 ). 45 Therefore, mapping required use of both conventional reference sequences to obtain the corresponding genomic coordinates.


#### RH

Relative to the conventional reference sequence for RHD ( L08429 ) the human reference genome is c.1136C>T (chr1:25,643,553C>T) p.Thr379Met, which corresponds to the family of DAU alleles, 46 specifically RHD*DAU0, which is primarily found in African Americans. 47 The conventional reference sequence ( DQ322275 ) for RHCE*ce ( RHCE*01) encodes a c+e+ phenotype. 46 , 47 , 48 The human reference genome RHCE sequence is c.48G>C, chr1:25,747,230G>C (p.Trp16Cys), 49 which corresponds to RHCE*ce(48C) ( RHCE*01.01), again, an allele more often found in African Americans.

Relative to the conventional reference sequence for RHD ( L08429 ) the human reference genome is c.1136C>T (chr1:25,643,553C>T) p.Thr379Met, which corresponds to the family of DAU alleles, 46 specifically RHD*DAU0, which is primarily found in African Americans. 47 The conventional reference sequence ( DQ322275 ) for RHCE*ce ( RHCE*01) encodes a c+e+ phenotype. 46 , 47 , 48 The human reference genome RHCE sequence is c.48G>C, chr1:25,747,230G>C (p.Trp16Cys), 49 which corresponds to RHCE*ce(48C) ( RHCE*01.01), again, an allele more often found in African Americans.


#### ACKRI previously DARC (FY)

The gene that encodes the Duffy antigens, Fy a and Fy b , has a minor 338 amino acid product (Variant 1, U01839 ) and a major 336‐amino‐acid product (Variant 2, NM_002036.3 ). 3 , 50 , 51 The nucleotide position responsible for the Fy a /Fy b phenotype is c.131G/A (p.Gly44Asp) in Variant 1 and c.125G/A (p.Gly42Asp) in Variant 2. 52 Some allele sources list the reference sequence as U01839 , 2 , 3 but many of the null allele nucleotide positions did not correlate with the U01839 sequence. The original report 52 used Variant 1 (which they did not deposit at the time of publication, but corresponds to NM_002036.3 ). The two sequences differ in length by six nucleotides, and both sequences have a GAC (Gly) codon six nucleotides upstream of the actual Fy a GAC (Gly) codon, making the disparity in reference sequence difficult to detect.

The gene that encodes the Duffy antigens, Fy a and Fy b , has a minor 338 amino acid product (Variant 1, U01839 ) and a major 336‐amino‐acid product (Variant 2, NM_002036.3 ). 3 , 50 , 51 The nucleotide position responsible for the Fy a /Fy b phenotype is c.131G/A (p.Gly44Asp) in Variant 1 and c.125G/A (p.Gly42Asp) in Variant 2. 52 Some allele sources list the reference sequence as U01839 , 2 , 3 but many of the null allele nucleotide positions did not correlate with the U01839 sequence. The original report 52 used Variant 1 (which they did not deposit at the time of publication, but corresponds to NM_002036.3 ). The two sequences differ in length by six nucleotides, and both sequences have a GAC (Gly) codon six nucleotides upstream of the actual Fy a GAC (Gly) codon, making the disparity in reference sequence difficult to detect.


#### FUT3

Relative to the conventional reference sequence ( X53578 ), the human reference genome sequence is a reported inactive form of the enzyme with nucleotide changes c.202T>C (chr19:5,844,649T>C) p.Trp68Arg and c.314C>T (chr19:5,844,537C>T) p.Thr105tMet corresponding to a Le(a−b−) phenotype. 53 

Relative to the conventional reference sequence ( X53578 ), the human reference genome sequence is a reported inactive form of the enzyme with nucleotide changes c.202T>C (chr19:5,844,649T>C) p.Trp68Arg and c.314C>T (chr19:5,844,537C>T) p.Thr105tMet corresponding to a Le(a−b−) phenotype. 53 


#### ACHE (YT)

 ACHE has several alternative splicing variants including: 1) the conventional cDNA reference sequence (Variant 1, M55040 , 614 amino acids) and 2) a cDNA sequence that is primarily expressed in erythroid tissue (Variant 2, NM_015831.2 , 617 amino acids). 54 , 55 Variant 1 and Variant 2 only differ in the C‐terminal region and the nucleotide numbering of the only known antigens (Yt a and Yt b ) are not affected by this difference. Published allele source lists the conventional cDNA reference sequence (Variant 1), but shows the amino acid sequence for Variant 2. 3 

 ACHE has several alternative splicing variants including: 1) the conventional cDNA reference sequence (Variant 1, M55040 , 614 amino acids) and 2) a cDNA sequence that is primarily expressed in erythroid tissue (Variant 2, NM_015831.2 , 617 amino acids). 54 , 55 Variant 1 and Variant 2 only differ in the C‐terminal region and the nucleotide numbering of the only known antigens (Yt a and Yt b ) are not affected by this difference. Published allele source lists the conventional cDNA reference sequence (Variant 1), but shows the amino acid sequence for Variant 2. 3 


#### FUT2

The FUT2 gene product has two isoforms: a 332‐amino‐acid short isoform and a 334‐amino‐acid long isoform (extra 11 amino acid N‐term). The original FUT2 paper found both isoforms, but although secretor mutations were referenced to the short isoform, only the long isoform was submitted ( U17894 ). 56 Subsequent alleles have continued to be referenced to the short isoform, but incorrectly list the long isoform as reference. 2 , 3 We took the long isoform (UCSC transcript: uc002pke.4) and removed the first 33 nucleotide (11 amino acids) so that the allele positions would correlate with those published.

The FUT2 gene product has two isoforms: a 332‐amino‐acid short isoform and a 334‐amino‐acid long isoform (extra 11 amino acid N‐term). The original FUT2 paper found both isoforms, but although secretor mutations were referenced to the short isoform, only the long isoform was submitted ( U17894 ). 56 Subsequent alleles have continued to be referenced to the short isoform, but incorrectly list the long isoform as reference. 2 , 3 We took the long isoform (UCSC transcript: uc002pke.4) and removed the first 33 nucleotide (11 amino acids) so that the allele positions would correlate with those published.


#### CR1 (KN)

Relative to the conventional reference sequence ( Y00816 ), the human reference genome is c.4828T>A (chr1:207,782,916T>A) p.Ser1610Thr, which corresponds to the allele encoding lack of the high frequency Knops antigen (Sl3) and a Sl3− (Sl:1,−2,−3) phenotype. 57 The Exome Variant Server 58 was used to determine the allele frequency for c.4828T>A, which is 2.5% (207/8041) European Americans and 0.4% (16/3818) African Americans.

Relative to the conventional reference sequence ( Y00816 ), the human reference genome is c.4828T>A (chr1:207,782,916T>A) p.Ser1610Thr, which corresponds to the allele encoding lack of the high frequency Knops antigen (Sl3) and a Sl3− (Sl:1,−2,−3) phenotype. 57 The Exome Variant Server 58 was used to determine the allele frequency for c.4828T>A, which is 2.5% (207/8041) European Americans and 0.4% (16/3818) African Americans.


#### GCNT2 (I)

Relative to the conventional reference sequence for GCNT2 ( AF458026 ), the human reference genome is c.816G>C (chr6:10,587,038G>C) p.Glu272Asp, which according to one source 2 is the null allele GCNT2*N.03 that encodes for an I− (i adult) phenotype associated with cataracts. However, although c.816G>C was found in an individual with an I− (i adult) phenotype, it was present with another change c.1006G>A, Gly336Arg ( GCNT2*N.04 ). 59 BGMUT indicates c.816G>C has been found in both adult I+ and I− (i adult) individuals. The Exome Variant Server 58 was used to determine the allele frequency for c.816G>C (dbSNP rs539351) as 0.1% (11/8589) European Americans and 0.05% (2/4404) African Americans.

Relative to the conventional reference sequence for GCNT2 ( AF458026 ), the human reference genome is c.816G>C (chr6:10,587,038G>C) p.Glu272Asp, which according to one source 2 is the null allele GCNT2*N.03 that encodes for an I− (i adult) phenotype associated with cataracts. However, although c.816G>C was found in an individual with an I− (i adult) phenotype, it was present with another change c.1006G>A, Gly336Arg ( GCNT2*N.04 ). 59 BGMUT indicates c.816G>C has been found in both adult I+ and I− (i adult) individuals. The Exome Variant Server 58 was used to determine the allele frequency for c.816G>C (dbSNP rs539351) as 0.1% (11/8589) European Americans and 0.05% (2/4404) African Americans.


#### RHAG

Relative to the conventional reference sequence for RHAG ( X64594 ) the human reference genome is c.724G>A (chr6:49,582,483G>A) p.Asp242Asn. However, aside from the original RHAG report ( X64594 ), 60 all subsequent sequences are c.724A p.Asn242 ( AF031549 , AF179682 , AF179684 , AF179685 , AF187847 , AF178841 ), and dbSNP indicates that c.742A p.Asn242 (rs1058063) has an allele frequency of 100% and is found in 590 of 590 tested chromosomes from a mix of Europeans, Asians, and Africans. Therefore, the c.724G in X64594 was likely a sequencing error with c.724A being the correct nucleotide.

Relative to the conventional reference sequence for RHAG ( X64594 ) the human reference genome is c.724G>A (chr6:49,582,483G>A) p.Asp242Asn. However, aside from the original RHAG report ( X64594 ), 60 all subsequent sequences are c.724A p.Asn242 ( AF031549 , AF179682 , AF179684 , AF179685 , AF187847 , AF178841 ), and dbSNP indicates that c.742A p.Asn242 (rs1058063) has an allele frequency of 100% and is found in 590 of 590 tested chromosomes from a mix of Europeans, Asians, and Africans. Therefore, the c.724G in X64594 was likely a sequencing error with c.724A being the correct nucleotide.


### Comprehensive whole genome antigen prediction

WGS data from a 47‐year‐old female of European ethnicity in generally good health were first analyzed to determine the sequencing coverage of the genes encoding RBC and PLT antigens. For genes encoding the RBC antigens there was an average coverage of 34× over 1,091,334 bp (Fig. 2 , Fig. S1 [available as supporting information in the online version of this paper], Tables 1 and 3 ). For genes encoding PLT antigens, there was an average coverage of 38× over 323,222 bp (Fig. 2 , Fig. 1S, Table 4 ). There were some regions with missing sequence coverage and/or poor sequencing quality in the following RBC genes: RHD (Exon 8), C4B , C4A , and CR1 (Fig. 2 , Fig. 1S). However, all of the RBC and PLT genes had adequate sequencing coverage (Fig. 1S) and quality to allow for prediction of phenotypes from the known allele nucleotide positions. The low coverage for RHD Exon 8 is likely due to the human reference genome Exon 8 containing a mismatched RHD*DAU0 allele change. In addition, without the presence of the RHD*DAU0 allele, Exon 8 is identical in both RHD and RHCE . Therefore, RHD Exon 8 sequences either misaligned to RHD and/or did not align at all.

Variant calling on WGS data determined the nucleotide positions that differed in relation to the human reference genome. The sequence alignments between the human reference genome CDS and the cDNA reference sequence were then used as a guide to convert genomic coordinates from the variant calling process into the conventional CDS positions. By combining the human reference genome antigen predictions with manual identification of the CDS converted variants using published allele tables, 2 , 3 , 4 , 10 , 12 , 23 the WGS data were used to comprehensively predict all RBC and PLT antigens (Tables 3 and 4 ). As part of the process, nucleotide changes were found that are not known to encode antigenic epitopes; while most were silent changes that did not alter the amino acid sequence, there were a few missense changes that do alter the amino acid sequence (Table 5 ). A RBC sample was tested for RBC antigens using available commercial serologic typing reagents and all of the antigen predictions were correct for the serologically tested RBC antigens (ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s).

WGS data from a 47‐year‐old female of European ethnicity in generally good health were first analyzed to determine the sequencing coverage of the genes encoding RBC and PLT antigens. For genes encoding the RBC antigens there was an average coverage of 34× over 1,091,334 bp (Fig. 2 , Fig. S1 [available as supporting information in the online version of this paper], Tables 1 and 3 ). For genes encoding PLT antigens, there was an average coverage of 38× over 323,222 bp (Fig. 2 , Fig. 1S, Table 4 ). There were some regions with missing sequence coverage and/or poor sequencing quality in the following RBC genes: RHD (Exon 8), C4B , C4A , and CR1 (Fig. 2 , Fig. 1S). However, all of the RBC and PLT genes had adequate sequencing coverage (Fig. 1S) and quality to allow for prediction of phenotypes from the known allele nucleotide positions. The low coverage for RHD Exon 8 is likely due to the human reference genome Exon 8 containing a mismatched RHD*DAU0 allele change. In addition, without the presence of the RHD*DAU0 allele, Exon 8 is identical in both RHD and RHCE . Therefore, RHD Exon 8 sequences either misaligned to RHD and/or did not align at all.


* WGS‐based RBC and PLT gene sequencing. Circos plot  61  of the WGS data that has been filtered to only show the RBC and PLT genes with a circular plot of the sequence coverage (100‐bp bins). *


*Comprehensive RBC antigen prediction from a patient's whole genome a *


**System** | **Gene** | **Average coverage** | **Phenotypes**
001 ABO |  FUT1, ABO  | 27×, 31× | A1
002 MNS |  GYPA  | 41× | M+N+, Vr−, Mt(a−), Ri(a−), Ny(a−), Or−, ERIK−, Os(a−), ENEP+, ENEH+, ENAV+, ENEV+, MNTD−
 GYPB  | 45× | S+s+, U+, En(a+), He−, Mi(a−), Mur−, Mv−, s(D−), Mit−, Dantu−
003 P1PK |  A4GALT  | 29× | P1+/P1−, pk+, NOR−
004 RH | RHD | 34× | D+, Tar−
 RHCE  | 33× | C−c+E+e−, C W −, C X −, E W −, V−, VS−, Rh26+LOCR−, Be(a−), DAK−, Go(a−), Rh32−, Crawford−CELO+, JAL−CEST+, STEM−, JAHK−
005 LU |  BCAM(LU), KLF1, GATA1  | 24×, 21×, 25× | Lu(a−b+), LURC+, Lu4+, Lu5+, Lu6+, Lu7+, Lu8+, Lu13+, Lu16+, Lu17+, Au(a+b−), Lu20+, Lu21+
006 KEL |  KEL  | 33× | K−k+, Kp(a−b+c−), Js(a−b+), Ul(a−), K11+, K12+, K13+, K14+, K18+, K19+, K22+, K23−, VLAN−VONG−, TOU+, RAZ+, KALT+, KTIM+, KYO−, KUCI+, KANT+, KASH+, KELP+, KETI+, KHUL+
007 LE |  FUT2,3  | 28×, 28×, 27×, 23× | Le(a+b−)
008 FY |  ACKR1(DARC)  | 28× | Fy(a+b+)
009 JK |  SLC14A1  | 37× | Jk(a+b+)
010 DI |  SLC4A1  | 26× | Di(a−b+), Wr(a−b+), Wd(a−), Rb(a−), WARR−, ELO−, Bp(a−), Mo(a−), Hg(a−), Vg(a−), Sw(a−), BOW−, NFLD−, Jn(a−), KREP−, Tr(a−), Fr(a−), SW1−, Wu−DISK+
011 YT |  ACHE  | 23× | Yt(a+b−)
013 SC |  ERMAP  | 37× | Sc1+Sc2−, Rd−, STAR+, SCER+, SCAN+
014 DO |  ART4  | 40× | Do(a+b+), Jo(a+), DOYA+, Hy+, DOMR+, DOLG+
015 CO |  AQP1  | 27× | Co(a+b−), Co4+
016 LW |  ICAM4  | 23× | LW(a+b−)
017 CH/RG |  C4B  | 25× | Ch1+, Ch2+, Ch3+, Ch4+, Ch5+, Ch6+, Rg1−, Rg2−
017 CH/RG |  C4A  | 25× | Ch1−, Ch2−, Ch3−, Ch4−, Ch5−, Ch6−, Rg1+, Rg2+
018 H |  FUT1,2,SLC35C1  | 27×, 28×, 29× | H+
019 XK |  XK  | 39× | Kx+
020 GE |  CYPC  | 32× | Ge2+, Ge3+, Ge4+, Es(a+), Wb−, An(a−), Dh(a−), GEIS−, GELP+, GEAT+, GETI+
021 CROM |  CD55  | 43× | Cr(a+), Tc(a+b−c−), Dr(a+), Es(a+), WES(a−b+), UMC+, GUTI+, SERF+, ZENA+, CROV+, CRAM+, CROZ+
022 KN |  CR1  | 35× | Kn(a+b−), McC(a+b−), Sla+Vil−, Yk(a+), Sl3+, KCAM+/KCAM−
023 IN |  CD44  | 39× | In(a−b+), INFI+, INJA+
024 OK |  BSG  | 22× | Ok(a+), OKGV+, OKVM+
025 RAPH |  CD151  | 22× | MER2+
026 JMH |  SEMA7A  | 27× | JMHK+, JMHL+, JMHG+, JMHM+, JMHQ+
027 I |  GCNT2  | 37× | I+
028 GLOB |  B3GALNT1  | 40× | P+
029 GIL |  AQP3  | 27× | GIL+
030 RHAG |  RHAG  | 39× | Duclos+, Ol(a−), DSLK+, RHAG4−
031 FORS |  GBGT1  | 27× | FORS+
032 JR |  ABCG2  | 37× | Jra+
033 LAN |  ABCB6  | 29× | Lan+
034 VEL |  SMIM1  | 22× | Vel+
035 CD59 |  CD59  | 36× | CD59.1+
036 AT |  SLC29A1  | 28× | At(a+)


*Comprehensive PLT antigen prediction from a patient's whole genome*


**Gene** | **Average coverage** | **Predicted HPA phenotypes**
 ITGB3  | 34× | 1a+, 1b+, 4a+, 4b−, 6bw−, 7bw−, 8bw−, 10bw−, 11bw−, 14bw−, 16bw−, 17bw−, 19w−, 21w−, 23bw−, 26bw−
 GP1BA  | 25× | 2a+, 2b−
 ITGA2B  | 27× | 3a+, 3b−, 9bw−, 20w−, 22bw−, 24bw−, 27bw−, 28bw−
 ITGA2  | 40× | 5a+, 5b−, 13bw−, 18w−, 25bw−
 GP1BB  | 21× | 12bw−
 CD109  | 39× | 15a−, 15b+

Variant calling on WGS data determined the nucleotide positions that differed in relation to the human reference genome. The sequence alignments between the human reference genome CDS and the cDNA reference sequence were then used as a guide to convert genomic coordinates from the variant calling process into the conventional CDS positions. By combining the human reference genome antigen predictions with manual identification of the CDS converted variants using published allele tables, 2 , 3 , 4 , 10 , 12 , 23 the WGS data were used to comprehensively predict all RBC and PLT antigens (Tables 3 and 4 ). As part of the process, nucleotide changes were found that are not known to encode antigenic epitopes; while most were silent changes that did not alter the amino acid sequence, there were a few missense changes that do alter the amino acid sequence (Table 5 ). A RBC sample was tested for RBC antigens using available commercial serologic typing reagents and all of the antigen predictions were correct for the serologically tested RBC antigens (ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s).


*Changes not known to encode new or altered antigenic epitopes*


**Gene** | **CDS nucleotide (genomic coordinate) and [amino acid]**
 GYPA  | hom c.38(chr4:145,041,741)A>C [missense p.Glu13Ala] Note: aa position 13 is within the N‐term of protein which is cleaved from the native protein.
 A4GALT  | het c.109(chr22:43,089,849)A>G [missense p.Met37Val]
 CR1  | het c.3623(chr1:207,753,621)A>G [missense p.His1208Arg]; het c.5480(chr1:207,790,088)C>G [missense p.Pro1827Arg]; hom c.5905(chr1:207,795,320)A>G [missense p.Thr1969Ala]
 CD109  | hom c.3722(chr6:74,521,947)C>T [missense p.Thr1241Met]


## DISCUSSION


### Advantages of antigen prediction by WGS

In this analysis we showed that it is possible to perform comprehensive RBC and PLT antigen prediction using WGS data. WGS‐based antigen prediction has advantages over current methods such as DNA CHIP, polymerase chain reaction, and Sanger sequencing. Although the current commercial DNA chip‐based assays enable antigen prediction, they are limited in the number of SNPs analyzed, which impacts unambiguous allele resolution. Assays for the RH blood group system are not capable of detecting all known variant RH alleles and additional assays need to be performed to determine RHD zygosity. Sanger sequencing could be used to determine all of the known alleles, but the method is labor‐intensive and requires the development and validation of many individual assays. In contrast, NGS‐based sequencing can evaluate whole gene sequences and detect gene rearrangements, and copy number analysis could determine zygosity. Laboratories could use whole genome or exome approaches or develop targeted NGS‐based panels that allow for more affordable sequencing of specific genomic regions by pooling patient specimens using molecular barcodes. In addition, the current generation of benchtop NGS instruments have a 24‐ to 48‐hour turnaround time.

In this analysis we showed that it is possible to perform comprehensive RBC and PLT antigen prediction using WGS data. WGS‐based antigen prediction has advantages over current methods such as DNA CHIP, polymerase chain reaction, and Sanger sequencing. Although the current commercial DNA chip‐based assays enable antigen prediction, they are limited in the number of SNPs analyzed, which impacts unambiguous allele resolution. Assays for the RH blood group system are not capable of detecting all known variant RH alleles and additional assays need to be performed to determine RHD zygosity. Sanger sequencing could be used to determine all of the known alleles, but the method is labor‐intensive and requires the development and validation of many individual assays. In contrast, NGS‐based sequencing can evaluate whole gene sequences and detect gene rearrangements, and copy number analysis could determine zygosity. Laboratories could use whole genome or exome approaches or develop targeted NGS‐based panels that allow for more affordable sequencing of specific genomic regions by pooling patient specimens using molecular barcodes. In addition, the current generation of benchtop NGS instruments have a 24‐ to 48‐hour turnaround time.


### Considerations for antigen prediction with WGS

Traditional serologic antigen testing for the most commonly tested antigens (ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s), performed independently and without knowledge of the WGS predictions, agreed with the WGS‐based antigen predictions. Although the prediction algorithms successfully predicted the ABO, C/c, M/N, and S/s antigens in this first genome analysis, it is anticipated that these antigens might be more challenging to reliably predict in patients with more extensive genomic variation. In general, robust and reliable automated algorithms for predicting ABO and other carbohydrate antigens require the integration of analyses across several genes. Furthermore, the known alleles for the carbohydrate antigens and the duplicated gene families GYPA / GYPB and RHD / RHCE often rely on multiple distant variant positions and haplotype ambiguities can occur due to the short read length of most current WGS platforms. Resolution of these ambiguities will ultimately require sequencing technologies that allow for longer read lengths, but in the meantime allele population prevalence could be used to select the most likely haplotype.

The correct alignment of NGS sequence reads is anticipated to be more difficult in the duplicated gene families GYPA / GYPB and RHD / RHCE . For example, the C antigen results from gene transfer of Exon 2 from RHD into RHCE , thus the NGS reads for a C+ RHCE Exon 2 might misalign to RHD Exon 2 without the appropriate algorithm. Similar issues with alignment are likely to occur with other gene rearrangements. However, it might be possible to use the sequence read depth along each gene to look for misaligned sequences to infer the correct antigen or find a rearrangement. NGS rearrangement detection algorithms 61 could also be used to look for the rearrangement breakpoint. Prediction algorithms capable of detecting RHD / RHCE rearrangements would be of great value in detecting these potential clinically significant changes in sickle cell patients and pregnant women with weak D or partial D phenotypes. Performing NGS‐based RBC predictions on a diverse population of serologically and conventionally molecularly typed individuals will aid development of interpretation algorithms.

Traditional serologic antigen testing for the most commonly tested antigens (ABO, D, c, C, e, E, K, k, Fy a , Fy b , Jk a , Jk b , M, N, S, and s), performed independently and without knowledge of the WGS predictions, agreed with the WGS‐based antigen predictions. Although the prediction algorithms successfully predicted the ABO, C/c, M/N, and S/s antigens in this first genome analysis, it is anticipated that these antigens might be more challenging to reliably predict in patients with more extensive genomic variation. In general, robust and reliable automated algorithms for predicting ABO and other carbohydrate antigens require the integration of analyses across several genes. Furthermore, the known alleles for the carbohydrate antigens and the duplicated gene families GYPA / GYPB and RHD / RHCE often rely on multiple distant variant positions and haplotype ambiguities can occur due to the short read length of most current WGS platforms. Resolution of these ambiguities will ultimately require sequencing technologies that allow for longer read lengths, but in the meantime allele population prevalence could be used to select the most likely haplotype.

The correct alignment of NGS sequence reads is anticipated to be more difficult in the duplicated gene families GYPA / GYPB and RHD / RHCE . For example, the C antigen results from gene transfer of Exon 2 from RHD into RHCE , thus the NGS reads for a C+ RHCE Exon 2 might misalign to RHD Exon 2 without the appropriate algorithm. Similar issues with alignment are likely to occur with other gene rearrangements. However, it might be possible to use the sequence read depth along each gene to look for misaligned sequences to infer the correct antigen or find a rearrangement. NGS rearrangement detection algorithms 61 could also be used to look for the rearrangement breakpoint. Prediction algorithms capable of detecting RHD / RHCE rearrangements would be of great value in detecting these potential clinically significant changes in sickle cell patients and pregnant women with weak D or partial D phenotypes. Performing NGS‐based RBC predictions on a diverse population of serologically and conventionally molecularly typed individuals will aid development of interpretation algorithms.


### Clinical benefits of antigen prediction with WGS

Oncology patients often receive RBC and PLT transfusions. For a minor added cost RBC and PLT antigen prediction could be added to NGS assays already being performed for oncologic diagnosis and drug selection. It might also be possible to replace the current SNP‐based antigen typing assays with targeted NGS‐based RBC and PLT predictions to aid in difficult serologic work‐ups and PLT refractory evaluations and help prevent alloantibody formation in chronically transfused patients. As clinical WGS becomes more commonplace for general disease screening and risk assessment, these existing WGS data could be used for large population level antigen prediction. This would allow for easy identification of donors; assist with compatibility testing of alloimmunized recipients; and prevent alloantibody formation using extended prophylactic matching and the identification of individuals at increased risk for posttransfusion purpura, hemolytic disease of the newborn or fetus, and neonatal alloimmune thrombocytopenia.

Oncology patients often receive RBC and PLT transfusions. For a minor added cost RBC and PLT antigen prediction could be added to NGS assays already being performed for oncologic diagnosis and drug selection. It might also be possible to replace the current SNP‐based antigen typing assays with targeted NGS‐based RBC and PLT predictions to aid in difficult serologic work‐ups and PLT refractory evaluations and help prevent alloantibody formation in chronically transfused patients. As clinical WGS becomes more commonplace for general disease screening and risk assessment, these existing WGS data could be used for large population level antigen prediction. This would allow for easy identification of donors; assist with compatibility testing of alloimmunized recipients; and prevent alloantibody formation using extended prophylactic matching and the identification of individuals at increased risk for posttransfusion purpura, hemolytic disease of the newborn or fetus, and neonatal alloimmune thrombocytopenia.


### Future directions

In this article, we have shown proof of principle that it is possible to comprehensively predict RBC and PLT antigens from WGS data. WGS‐based antigen predictions may someday enable accurate determination of blood group antigens, including ABO and RH, at a level of fidelity that cannot be achieved with current DNA chip analysis. To fully realize this potential, we are currently developing and validating prediction algorithms capable of automatically detecting and integrating across the known antigen alleles, which will allow for quick and easy antigen prediction from both WGS and targeted NGS. We are also extending our analysis algorithms for use with the newest human reference genome (GRCh38).

In this article, we have shown proof of principle that it is possible to comprehensively predict RBC and PLT antigens from WGS data. WGS‐based antigen predictions may someday enable accurate determination of blood group antigens, including ABO and RH, at a level of fidelity that cannot be achieved with current DNA chip analysis. To fully realize this potential, we are currently developing and validating prediction algorithms capable of automatically detecting and integrating across the known antigen alleles, which will allow for quick and easy antigen prediction from both WGS and targeted NGS. We are also extending our analysis algorithms for use with the newest human reference genome (GRCh38).


## CONFLICT OF INTEREST

Dr. Green's research is supported by grants from the National Institutes of Health and Illumina, Inc. Dr. Green has received compensation for advisory services or speaking from Invitae, Prudential, Arivale, Illumina, AIA, Helix and Roche. The other authors have disclosed no conflicts of interest.

Dr. Green's research is supported by grants from the National Institutes of Health and Illumina, Inc. Dr. Green has received compensation for advisory services or speaking from Invitae, Prudential, Arivale, Illumina, AIA, Helix and Roche. The other authors have disclosed no conflicts of interest.


## Supporting information
