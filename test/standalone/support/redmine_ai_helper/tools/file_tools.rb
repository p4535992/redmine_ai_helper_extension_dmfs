# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later

# Test double for AI Helper's public tool boundary. No Rails, RubyLLM provider,
# database, real attachment storage or external service is loaded by this suite.
# This intentionally does not implement AI Helper's DSL/schema internals.
module RedmineAiHelper
  module Tools
    # Projects granted to every provider instance, so code that creates a
    # provider internally (the DMSF page action) sees the same scope as the
    # tests instead of an empty one. Kept outside the class because class-level
    # instance variables are not inherited by DmsfTools.
    class << self
      attr_accessor :default_allowed_projects
    end

    class FileTools
      class UserError < StandardError; end

      class SchemaRecorder
        def property(*)
          nil
        end
      end

      class << self
        def function_registry
          @function_registry ||= {}
        end

        def define_function(name, description:, write: false, &block)
          function_registry[name] = { description: description, write: write }
          SchemaRecorder.new.instance_eval(&block) if block
        end
      end

      attr_accessor :allowed_projects
      attr_reader :llm_calls

      def initialize
        @allowed_projects = Array(RedmineAiHelper::Tools.default_allowed_projects)
        @llm_calls = []
      end

      def accessible_projects
        allowed_projects
      end

      def accessible_project?(project)
        allowed_projects.include?(project)
      end

      private

      def user_errors_as_result
        yield
      rescue UserError => error
        { error: error.message }
      end

      def analyze_with_llm(prompt:, file_paths:)
        @llm_calls << { prompt: prompt, file_paths: file_paths }
        "Document summary from the test model"
      end
    end
  end
end
