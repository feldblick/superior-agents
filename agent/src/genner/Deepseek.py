import re
from typing import List, Tuple

import yaml
from loguru import logger
from openai import OpenAI
from result import Err, Ok, Result

from src.config import DeepseekConfig
from src.helper import extract_content
from src.types import ChatHistory

from .Base import Genner


class DeepseekGenner(Genner):
	def __init__(self, client: OpenAI, config: DeepseekConfig):
		super().__init__("deepseek")
		self.client = client
		self.config = config

	def ch_completion(self, messages: ChatHistory) -> Result[str, str]:
		response = ""

		try:
			response = self.client.chat.completions.create(
				model=self.config.model,
				messages=messages.as_native(),  # type: ignore
				stream=False,
				max_tokens=self.config.max_tokens
			)

			final_response = response.choices[0].message.content
		except AssertionError as e:
			return Err(f"DeepseekGenner.ch_completion: {e}")
		except Exception as e:
			return Err(
				f"DeepseekGenner.ch_completion: An unexpected error while generating code with {self.config.name}, response: {response} occured: \n{e}"
			)

		return Ok(final_response)

	def generate_code(
		self, messages: ChatHistory, blocks: List[str] = [""]
	) -> Result[Tuple[List[str], str], str]:
		try:
			completion_result = self.ch_completion(messages)

			if err := completion_result.err():
				return Err(
					f"OllamaGenner.generate_code: completion_result.is_err(): \n{err}"
				)

			raw_response = completion_result.unwrap()

			extract_code_result = self.extract_code(raw_response, blocks)

			if err := extract_code_result.err():
				return Err(
					f"DeepseekGenner.generate_code: extract_code_result.is_err(): \n{err}"
				)

			processed_code = extract_code_result.unwrap()
		except Exception as e:
			return Err(
				f"An unexpected error while generating code with {self.config.name}, occured: \n{e}"
			)

		return Ok((processed_code, raw_response))

	def generate_list(
		self, messages: ChatHistory, blocks: List[str] = [""]
	) -> Result[Tuple[List[List[str]], str], str]:
		try:
			completion_result = self.ch_completion(messages)

			if err := completion_result.err():
				return Err(
					f"DeepseekGenner.generate_list: completion_result.is_err(): \n{err}"
				)

			raw_response = completion_result.unwrap()

			extract_list_result = self.extract_list(raw_response, blocks)

			if err := extract_list_result.err():
				return Err(
					f"DeepseekGenner.generate_list: extract_list_result.is_err(): \n{err}"
				)

			extracted_list = extract_list_result.unwrap()
		except Exception as e:
			return Err(
				f"An unexpected error while generating list with {self.config.name}, raw response: {raw_response} occured: \n{e}"
			)

		return Ok((extracted_list, raw_response))

	@staticmethod
	def extract_code(response: str, blocks: List[str] = [""]) -> Result[List[str], str]:
		extracts: List[str] = []

		for block in blocks:
			# Extract code from the response
			try:
				response = extract_content(response, block)
				regex_pattern = r"```python\n([\s\S]*?)```"
				code_match = re.search(regex_pattern, response, re.DOTALL)

				assert code_match is not None, "No code match found in the response"
				assert (
					code_match.group(1) is not None
				), "No code group number 1 found in the response"

				code = code_match.group(1)
				assert isinstance(code, str), "Code is not a string"

				extracts.append(code)
			except AssertionError as e:
				return Err(f"DeepseekGenner.extract_code: Regex failed: {e}")
			except Exception as e:
				return Err(
					f"An unexpected error while extracting code occurred, raw response: {response}, error: \n{e}"
				)

		return Ok(extracts)

	@staticmethod
	def extract_list(
		response: str, blocks: List[str] = [""]
	) -> Result[List[List[str]], str]:
		extracts: List[List[str]] = []

		for block in blocks:
			try:
				response = extract_content(response, block)
				# Remove markdown code block markers and find yaml content
				# Updated regex pattern to handle triple backticks
				regex_pattern = r"```yaml\n(.*?)```"
				yaml_match = re.search(regex_pattern, response, re.DOTALL)

				assert yaml_match is not None, "No match found"
				yaml_content = yaml.safe_load(yaml_match.group(1).strip())
				assert isinstance(yaml_content, list), "Yaml content is not a list"
				assert all(
					isinstance(item, str) for item in yaml_content
				), "All yaml content items must be strings"

				extracts.append(yaml_content)
			except AssertionError as e:
				logger.error(f"DeepseekGenner.extract_list: Assertion error: {e}")
				return Err(f"DeepseekGenner.extract_list: Assertion error: {e}")
			except Exception as e:
				logger.error(
					f"An unexpected error while extracting code occurred, raw response: {response}, error: \n{e}"
				)
				return Err(
					f"An unexpected error while extracting code occurred, raw response: {response}, error: \n{e}"
				)

		return Ok(extracts)