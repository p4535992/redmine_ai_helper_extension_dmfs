# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

# Run against an existing, migrated Redmine installation with AI Helper and
# this extension installed. This is a real-environment registration smoke
# check, not a substitute for document/ACL integration tests.
#
# From the Redmine root:
#   RAILS_ENV=test bundle exec ruby plugins/redmine_ai_helper_extension_dmfs/test/redmine_smoke.rb
#
# For a script stored outside plugins, also set REDMINE_ROOT=/path/to/redmine.
# The assertions below perform no document search, download, LLM request,
# setting update or database migration. Redmine boots normally first.

unless defined?(Rails) && Rails.application&.initialized?
  ENV["RAILS_ENV"] ||= "test"
  redmine_root = ENV.fetch("REDMINE_ROOT") { File.expand_path("../../..", __dir__) }
  environment = File.join(redmine_root, "config/environment.rb")
  abort "Redmine environment not found; set REDMINE_ROOT to the Redmine installation." unless File.file?(environment)

  require environment
end

require "ostruct"

module RedmineAiHelperDmsfSmoke
  # Abort on the first failed contract; never present a partial run as success.
  def self.check(label, condition)
    raise "FAIL: #{label}" unless condition

    puts "PASS: #{label}"
  end

  def self.run
    plugin = Redmine::Plugin.find(:redmine_ai_helper_extension_dmfs)
    check("plugin version", plugin.version == RedmineAiHelperDmsf::VERSION)

    agent_class = RedmineAiHelperDmsf::DmsfExtensionAgent
    tools_class = RedmineAiHelperDmsf::DmsfTools
    registered = RedmineAiHelper::AgentList.instance.find_agent("dmsf_extension_agent")
    check("automatic agent registration", registered && registered[:class] == agent_class.name)

    # BaseAgent#initialize constructs an LLM provider. Allocate without calling
    # it because the tested methods need no provider, project or conversation.
    agent = agent_class.allocate
    check("extension tool provider", agent.available_tool_providers == [tools_class])
    check("exactly three tool definitions",
          tools_class.function_registry.keys.sort == %i[analyze_file search_files summarize_folder])
    tool_classes = tools_class.tool_classes
    check("exactly three generated tools", tool_classes.length == 3)
    check("all tools are read-only", tool_classes.all? { |tool| tool.write_tool? == false })

    settings = AiHelperSetting.order(:id).first
    raise "Configure AI Helper settings in this environment before running the smoke check." unless settings

    expected_enabled = !!(tools_class.available? && ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] == "1" &&
                          settings.attachment_send_enabled?)
    check("tools follow current activation settings", tools_class.enabled? == expected_enabled)
    check("agent follows current activation settings", agent.enabled? == expected_enabled)
    puts "DMSF agent state: #{expected_enabled ? 'enabled' : 'disabled'}"

    check_settings_page_integration
    check_document_action(tools_class)
    check_backstories(agent)
    puts "Registration smoke checks passed; document access and model execution were not exercised."
  end

  # The page action is offered by a layout hook, because DMSF has no view hook
  # on its document or folder page. Verify registration, the rendered partial and
  # the negative case without touching a real page.
  def self.check_document_action(tools_class)
    listeners = Redmine::Hook.hook_listeners(:view_layouts_base_body_bottom)
    check("layout hook is registered", listeners.any? { |listener| listener.is_a?(RedmineAiHelperDmsf::ViewHook) })

    partial = File.join(Redmine::Plugin.find(:redmine_ai_helper_extension_dmfs).directory,
                        "app/views/redmine_ai_helper_dmsf/_document_action.html.erb")
    check("document action partial exists", File.file?(partial))

    %i[en it ja].each do |locale|
      check("#{locale} document action label", !I18n.t("redmine_ai_helper_dmsf.document_action.label",
                                                        locale: locale, default: nil).to_s.empty?)
    end

    other_page = OpenStruct.new(controller_name: "issues", action_name: "show")
    check("action is not offered outside DMSF", RedmineAiHelperDmsf::DocumentAction.target(other_page).nil?)

    # An unsaved document has no project or revision, so the action must be
    # refused. The positive path needs real DMSF data and is covered by the
    # laboratory smoke check.
    check("document action is hidden without document access",
          tools_class.new.document_action_visible?(DmsfFile.new) == false)
  end

  # The extension settings are rendered inside AI Helper's own settings page.
  # Verify registration, normalization and the rendered tab without saving.
  def self.check_settings_page_integration
    key = RedmineAiHelperDmsf::Settings::FULL_TEXT_SEARCH_KEY
    values = RedmineAiHelperDmsf::Settings.values
    check("full-text search setting is normalized", %w[0 1].include?(values[key]))
    check("full-text search setting is read as a boolean",
          RedmineAiHelperDmsf::Settings.full_text_search_enabled? == (values[key] == "1"))

    plugin = Redmine::Plugin.find(:redmine_ai_helper_extension_dmfs)
    check("plugin settings are declared", plugin.settings[:default].is_a?(Hash))
    check("plugin has no separate settings screen", plugin.configurable? == false)
    check("AI Helper settings helper is patched",
          AiHelperSettingsHelper < RedmineAiHelperDmsf::Patches::AiHelperSettingsHelperPatch)
    check("AI Helper settings controller is patched",
          AiHelperSettingsController < RedmineAiHelperDmsf::Patches::AiHelperSettingsControllerPatch)

    tabs = AiHelperSettingsController.new.view_context.ai_helper_settings_tabs(nil)
    check("DMSF tab is appended to AI Helper settings", tabs.last[:name] == "dmsf")
    partial = File.join(plugin.directory, "app/views/redmine_ai_helper_dmsf/_settings_tab.html.erb")
    check("DMSF settings tab partial exists", File.file?(partial))
  end

  def self.check_backstories(agent)
    key = "redmine_ai_helper_dmsf.agent_backstory"
    upstream_loader = RedmineAiHelper::Util::PromptLoader.singleton_class
    upstream_calls = []
    tracer = TracePoint.new(:call) do |event|
      upstream_calls << event.method_id if event.defined_class == upstream_loader && event.method_id == :load_template
    end

    tracer.enable do
      %i[en it ja].each do |locale|
        I18n.with_locale(locale) do
          expected = backstory_text(locale)
          check("#{locale} backstory uses extension translations", agent.backstory == expected && !expected.empty?)
        end
      end

      # Use a real Redmine locale without an extension-specific translation.
      # Do not change global locale validation, fallback settings or translations.
      fallback_locale = I18n.available_locales.find do |locale|
        !%i[en it ja].include?(locale.to_sym) && !I18n.exists?(key, locale, fallback: false)
      end
      if fallback_locale
        I18n.with_locale(fallback_locale) do
          check("English backstory fallback", agent.backstory == backstory_text(:en))
        end
      else
        puts "SKIP: English fallback (no untranslated Redmine locale is enabled)"
      end
    end
    check("backstory is independent of upstream prompt files", upstream_calls.empty?)
  end

  # The agent joins every instruction key it knows; a missing translation is
  # skipped, so the expectation mirrors that contract.
  # @param locale [Symbol] locale to read
  # @return [String] expected backstory
  def self.backstory_text(locale)
    %w[agent_backstory agent_backstory_folders].filter_map do |name|
      I18n.t("redmine_ai_helper_dmsf.#{name}", locale: locale, default: nil)
    end.join("\n")
  end
end

# Reject accidental writes from settings access during assertions. In particular,
# upstream's settings getter otherwise creates a record when none exists.
ActiveRecord::Base.while_preventing_writes { RedmineAiHelperDmsfSmoke.run }
