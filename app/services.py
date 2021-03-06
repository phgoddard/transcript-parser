import os
import re
import db.mysql_repository

class Services():
    def __init__(self):
        self.repo = db.mysql_repository.MysqlRepository()
        self.study_id = -1

    def checkifstudy(self, studyname) -> int:
        study_id = self.repo.checkifstudyexists(studyname)
        if study_id == []:
            study_id = self.repo.create_study(studyname)
        self.study_id = study_id[0]
        self.s = Study(studyname, study_id[0])
        return study_id

    def get_file(self, file_name):
        self.f = File(file_name,self.study_id)
        self.repo.save_file(self.f)
        return self.f.all_text

    def get_dialog(self, output_filename):
        d = Dialog(output_filename, self.f.file_id, self.f.all_text)
        d.saveDialog(d.dialogdata_for_sql, output_filename)
        self.repo.save_dialog(d)
        return d.dialogdata_for_sql[1:]

class Study():
    #store study name and id for any study that has research associated with it
    def __init__(self, studyname: str, study_id: int):
        #class variables
        self.studyname = studyname
        self.study_id = study_id

class File():
    #store file metadata and the original text from the file
    def __init__(self, file_name: str, study_id):
        # class level variables
        self.cwd = ""
        self.WorkingDir = ""
        self.file_id = -1
        self.file_name = file_name
        self.study_id = study_id
        self.stuff = ""
        self.morestuff = ""
        self.all_text = []           #original text is read as lines
        #class methods
        self.WorkingDir = self.changeWorkingDir()
        self.all_text = self.readFile()

    def changeWorkingDir(self):
        self.WorkingDir = os.chdir('/data/cxdata')
        """
        docker cp /users/tandemseven/cxdata
        docker cp / root / some - file.txt some - docker - container: / root
        This will copy the file some - file.txt in the directory / root on your host machine into the Docker container named 
        some - docker - container into the directory / root. It is very
        close to the secure copy syntax.And as shown in the previous post, you can use it
        vice versa.I.e., you also copy files from the container to the host.
        """
        return self.WorkingDir

    def readFile(self):
        #first data file created: -> all_text
        self.inFile = open(self.file_name,'r')
        self.stuff = self.inFile.read()
        self.morestuff = ''.join(self.stuff)
        self.morestuff = self.morestuff.split("'")
        self.all_text = "\\'".join(self.morestuff)
        return self.all_text

class Dialog():
    '''
    Dialog ingests a transcript consisting of an interview between an interviewer and respondent
    Users specify the filename ana assumes the file is in the current working directory
    Methods do the following:
    1 - read
    2 - remove newlines and junk numbers
    3 - Find the speakers (there may be more than 2)
    4 - Extracts the timestamps
    5 - Extracts into two lists the dialog for the interviewer and the respondent
    6 - Removes file meta-data (e.g. the transcript tool name)
    7 -
    '''
    def __init__(self, output_filename, file_id, inputdata):
        self.file_id = file_id
        self.output_filename = output_filename
        self.cleanListText = []         #new lines and extraneous int digits are stripped
        self.dialogdata_for_sql = []    #List of lists of rows [[0,'speaker name','dialog text.....'],[1,'speakername','text...']...]
        self.noTimeStampsText = []      #all timestamps are removed
        self.speaker = ""
        self.speakers = []              #acculumative list of all references to speakers of dialog
        self.speakerSet = set           #just the set of unique speakers is stored
        self.speakerList = []           #set is converted to list
        self.speaker_segments = []      #list of dialog for a given speaker
        self.metaData = []              #everything before the first timestamp
        self.questions = []             #all dialog from the interviewer
        self.responses = []             #all dialog from the respondent

        #initialized class methods

        self.cleanNLandNumbers(inputdata)
        self.dialogdata_for_sql = self.format_for_sql()
        self.noTimeStampsText = self.cleanTimeStamps()
        self.speakerSet = self.getSpeakers()
        self.cleanListText = self.getMetaData()

    def cleanNLandNumbers(self,filedata):
        #removes newlines and integer IDs for snippet of dialog: -> cleanListText
        filedata = filedata.splitlines()
        while ("" in filedata):
            filedata.remove("")
        self.rx = ('\d\d*')
        for line in filedata:
            if line != "\n" and not re.search(self.rx,line):
                self.cleanListText.append(line.strip())

    def format_for_sql(self):
        self.speaker = ""
        self.textline = ""
        self.rgSpeaker = '[A-za-z]+ ?[A-Za-z]+:'
        self.rgtextline = ':.*'
        self.rgjusttext = '.*'

        print(self.cleanListText)
        self.rownum = 0
        for line in self.cleanListText:
            #print(line)
            self.row = []
            if ":" in line:
                self.smatch = re.search(self.rgSpeaker, line)
                if self.smatch != None:
                    self.speaker = self.smatch.group()

                self.smatch = re.search(self.rgtextline, line)
                if self.smatch != None:
                    self.textline = self.smatch.group()

                self.row.append(self.rownum)
                self.row.append(self.speaker[:-1])
                self.row.append(self.textline[2:])
                self.dialogdata_for_sql.append(self.row)
            else:
                self.smatch = re.search(self.rgjusttext, line)
                if self.smatch != None:
                    self.textline = self.smatch.group()
                    # print(rownum,textline)
                    self.row.append(self.rownum)
                    self.row.append(self.speaker[:-1])
                    self.row.append(self.textline)
                    self.dialogdata_for_sql.append(self.row)
            #print(self.row)
            self.rownum += 1
        return self.dialogdata_for_sql

    def cleanTimeStamps(self):
        self.rgTimestamp1 = '\d\d:\d\d:\d\d.\d\d\d --> \d\d:\d\d:\d\d.\d\d\d'
        for line in self.cleanListText:
            res = re.search(self.rgTimestamp1, line)
            if res:
                continue
            else:
                self.noTimeStampsText.append(line)

        return self.noTimeStampsText[1:]

    def getSpeakers(self):
        #reads cleanListText and finds speakers: -> speakerList
        self.rgSpeaker = '[A-za-z]+ ?[A-Za-z]+:'
        for line in self.cleanListText:
            self.smatch = re.search(self.rgSpeaker, line)
            if self.smatch != None:
                self.speakers.append(self.smatch.group())
        self.speakerSet = set(self.speakers)
        self.speakerList = sorted(list(self.speakerSet))
        return self.speakerList

    def getMetaData(self):
        #reads cleanListText and looks for first timestamp, then extracts metadata before it
        #strips metadata off and overwrites cleanListText with list of strings
        #includes timestamps
        i = 0
        self.rgTimestamp1 = '\d\d:\d\d:\d\d.\d\d\d --> \d\d:\d\d:\d\d.\d\d\d'
        while i < 5:
            self.metaData.append(self.cleanListText[i])
            self.res = re.search(self.rgTimestamp1, self.cleanListText[i])
            if self.res:
                self.cleanListText.pop()
                break
            i+=1
        return self.cleanListText[1:]

    def saveDialog(self, data: list, output_filename: str):
        #writes out cleanListText (both interviewer and respondent) with metadata
        self.outFile = open('/data/cxdata/' + output_filename,'w')
        self.outFile.write("Input file: ")
        self.outFile.write(output_filename + '\n')

        self.outFile.write("Speakers: ")
        for i in range(len(self.speakerList)):
            self.outFile.write(self.speakerList[i])
            self.outFile.write('\n')

        for sent in data:
            [self.outFile.write (str(s) + ", ") for s in sent]
            self.outFile.write('\n')
        self.outFile.close()


if __name__ == "__main__":
    services = Services()
    services.get_study()
    filedata = services.get_file()
    services.get_dialog(filedata)


