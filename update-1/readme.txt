Update 08-Jun-2019:
===================
Added a new recording mode/level 4 which only records when a CALL instruction was executed. This mode is great if you want to see only the DPS settings and the matching CALL results together. It saves you from deleting all the intermediate entries in the recording file. 

Related to this are 2 small modifications to the CALL instruction:
1. the command string itself is now also undergoing parameter substitution ($F ..), same as the parameters before.
2. the last parameter is no longer used for the command but instead passed as a comment into the recording file. 

Recording a comment (which can also be an image file name) is very convenient if you have two or more different CALL instructions in the same program
