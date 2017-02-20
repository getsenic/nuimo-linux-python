class InProgress(Exception):
	def __rep__(self):
		return "inprogress"

	def __str__(self):
		return "inprogress"


class Unknown(Exception):
	def __rep__(self):
		return "unknwown"

	def __str__(self):
		return "unknwown"
