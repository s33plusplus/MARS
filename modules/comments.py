# encoding: UTF-8

# Comments #
############

# Import #
##########

import re
import logging
import token
import wiki
import messages
from pprint import pprint
import time

# Variables #
#############

history = []

# Functions #
#############

# Starts the comments module
def start(data,msg,r):
	logging.debug("Starting Module: Comments")
	subreddit = get_sub(r,data["running_subreddit"]) # gets subreddit object
	sub_comments = sub_get_comments(subreddit) # gets x comments from sub
	process_comments(data,msg,r,sub_comments) # processes the comments

# Gets subreddit object from reddit
def get_sub(r,sub_name):
	logging.debug("Getting Subreddit")
	logging.info("Running in %s" % sub_name)
	return r.get_subreddit(sub_name)

# Gets the newest comments from the subreddit
def sub_get_comments(subreddit):
	logging.debug("Getting Comments")
	return subreddit.get_comments(limit=None) # Limits comments retrieved

# Comment Processing
def process_comments(data,msg,r,sub_comments):
	logging.debug("Processing Comments")
	running_username = str(data["running_username"]).lower()
	for comment in sub_comments: # for each comment in batch
		if comment not in history or comment.edited:
			history.append(comment)
			logging.debug("Comment History Count: " + str(len(history)))
			if not comment.banned_by: # Ignores removed comments
				comment_author = str(comment.author.name).lower()
				if comment_author != running_username: # Ignore my own comments
					logging.info("Searching comment by: %s\n%s" % (comment.author.name
						if comment.author else "[deleted]",comment.permalink)) # Shows redditor and permalink
					lines = split_comment(comment.body) # Gets comment lines
					token_found = search_line(data["token"],lines) # Checks for match
					if token_found: # Starts checks when a token is found
						logging.info("Token Found")
						start_checks(data,msg,r,comment,token_found)
					else:
						logging.info("No Token Found")
				else:
					logging.debug("Comment found was my own.")
				if comment_author == str(comment.submission.author).lower():
					print("Placeholder: Change Submission Flair")
			else:
				logging.debug("This comment was removed by a mod and has not been scanned.")
		if len(history) > 2000:
			del history[0]

# Starts Checks
def start_checks(data,msg,r,token_comment,token_found):
	logging.debug("Starting Checks")
	running_username = str(data["running_username"]).lower()
	awarder = str(token_comment.author.name).lower()
	awardee_comment = r.get_info(thing_id=token_comment.parent_id)
	if awardee_comment.author:
		awardee = str(awardee_comment.author.name).lower()
		if awardee == running_username: # Prevents reply to bot
			logging.info("User replied to me")
		elif awardee == awarder: # Prevents reply to self
			logging.info("User replied to self")
		elif check_already_replied(data,msg["confirmation"],token_comment.replies,running_username):
			logging.info("Already Confirmed")
		elif check_already_replied(data,msg["error_length"],token_comment.replies,running_username):
			if token_comment.edited:
				optional_checks(data,msg,r,token_comment,awarder,awardee_comment,awardee,token_found)
			else:
				logging.info("Already Notified - Too Short")
		elif check_already_replied(data,msg["error_bad_recipient"],token_comment.replies,running_username):
			logging.info("Already Notified - Bad Recipient")
		elif check_already_replied(data,msg["error_submission_history"],token_comment.replies,running_username):
			logging.info("Already Notified - Submission History Error")
		else:
			optional_checks(data,msg,r,token_comment,awarder,awardee_comment,awardee,token_found)
	else:
		logging.info("Unable to award token to deleted comment")

# Splits comments into lines for more thorough processing
def split_comment(body):
	logging.debug("Splitting Comment Body")
	return body.split("\n") # Splits double line breaks

# Search comment for symbol token
def search_line(data_token,lines):
	logging.debug("Searching Line For Token")
	for line in lines:
#		logging.debug("Debug Comment Line: " + line)
		#NOTE: Markup should be at the start of the line, and shouldn't contain HTML entities like &gt;
		if re.match("(^    |^>)",line) is None: # Don't look in code or quotes
			for token in data_token: # Check each type of token
				if token in line:
					return token

# Check to make sure I haven't already replied
def check_already_replied(data,msg,replies,running_username):
	logging.debug("Checking Already Replied")
	for reply in replies:
		try:
			if str(reply.author.name).lower() == running_username:
				if str(msg).lower()[0:10] in str(reply.body).lower():
					return True
		except:
			logging.debug("Check Failed")
			

# Optional checks based on configuration
def optional_checks(data,msg,r,token_comment,awarder,awardee_comment,awardee,token_found):
	logging.debug("Optional Checks")
	if check_awardee_not_author(data["check_ana"],token_comment.submission.author,awardee):
		error_bad_recipient = messages.error_bad_recipient(data,msg,token_comment)
		token_comment.reply(error_bad_recipient).distinguish()
		logging.info("Error Bad Recipient Sent")
	elif check_awarder_to_awardee_history(data,msg,r,awardee_comment,awardee,token_comment,awarder):
		error_submission_history = messages.error_submission_history(msg,awardee_comment.author.name)
		token_comment.reply(error_submission_history).distinguish()
		logging.info("Error Submission History Sent")
	elif check_length(data,token_comment.body,token_found):
		error_length = messages.error_length(data,msg,awardee_comment.author.name)
		token_comment.reply(error_length).distinguish()
		logging.info("Error Length Sent")
	else:
		logging.debug("Token Valid - Beginning Award Process")
		flair_count = token.start_increment(data,msg,r,awardee)
		logging.debug("Token Awarded")
		token_comment.save()
		logging.debug("Comment Saved")
		edited_reply = False
		for reply in token_comment.replies:
			if reply.author:
				logging.debug("Editing existing comment")
				if str(reply.author.name).lower() == data["running_username"].lower():
					confirmation = messages.confirm(data,msg,awardee_comment,awardee)
					reply.edit(confirmation).distinguish()
					edited_reply = True
		if edited_reply == False:
			logging.debug("Leaving new comment")
			confirmation = messages.confirm(data,msg,awardee_comment,awardee)
			token_comment.reply(confirmation).distinguish()
		logging.info("Confirmation Message Sent")
		wiki.start(data,r,token_comment,token_comment.author.name,awardee_comment.author.name,flair_count)
		logging.info("Wiki Updates Complete")
		wait()

def wait():
	wait_time = 35
	logging.debug("Sleeping for %s seconds to clear cache" % wait_time)
	time.sleep(wait_time)

# Check to ensure submission author is not receiving a token
def check_awardee_not_author(check_ana,sub_author,awardee):
	if check_ana == "1":
		logging.debug("Checking Awardee Not Author")
		return str(sub_author).lower() == str(awardee).lower()
	elif check_ana == "0":
		logging.debug("Check Recipient Not Author is disabled.")

# Checks to see if the awarder has already awarded the awardee in this thread
def check_awarder_to_awardee_history(data,msg,r,awardee_comment,awardee,token_comment,awarder):
	if data["check_history"] == "1":
		# TREE means it will only search the root comment and all replies
		logging.debug("Checking Awarder to Awardee History - TREE")
		root = awardee_comment
		while not root.is_root: # Move to the top comment
			root = r.get_info(thing_id=root.parent_id)
		if iterate_replies(data,msg,r,root,awardee,awarder):
			logging.info("Token awarded elsewhere in tree")
			return True
	elif data["check_history"] == "0":
		logging.debug("Check Awarder to Awardee History is disabled.")

# Iterates through the comment tree - VERY expensive
def iterate_replies(data,msg,r,comment,awardee,awarder):
	logging.debug("Iterating Replies")
	iterate = "Yes"
	msg_confirmation = msg["confirmation"]
	running_username = str(data["running_username"]).lower()
	try:
		comments = r.get_submission(comment.permalink).comments
	except:
		return iterate
	for comment in comments:
		if iterate == "Yes":
			if check_already_replied(data,msg_confirmation,comment.replies,running_username):
				if check_awarder(r,comment,awarder):
					if check_awardee(r,comment,awardee):
						iterate = "No"
						return iterate
			for reply in comment.replies:
				iterate = iterate_replies(data,msg,r,reply,awardee,awarder)
				if iterate == "No":
					return iterate
		elif iterate == "No":
			# Not sure this is ever called
			print("Comment NoIteration Called - Remove this line and comment")
			logging.critical("Comment NoIteration Called - Remove this line and comment")
			return iterate

# Checks original awarder against recently found awarder
def check_awarder(r,comment,orig_awarder):
	logging.debug("Checking Awarder")
	try:
		awarder = str(comment.author.name).lower()
	except:
		awarder = "[deleted]"
	if awarder == orig_awarder:
		return True

# Checks original awardee against recently found awardee
def check_awardee(r,comment,orig_awardee):
	logging.debug("Checking Awardee")
	awardee_comment = r.get_info(thing_id=comment.parent_id)
	try:
		awardee = str(awardee_comment.author.name).lower()
	except:
		awardee = "[deleted]"
	if awardee == orig_awardee:
		return True

# Check length of comment against minimum requirement
def check_length(data,body,token_found):
	if data["check_length"] == "1":
		logging.debug("Checking Comment Length")
		if token_found != "force":
			return len(body) < int(data["min_length"]) + len(token_found)
	elif data["check_length"] == "0":
		logging.debug("Check Comment Length is disabled.")

# EOF
