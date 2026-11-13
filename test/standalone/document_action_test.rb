# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later

require_relative "test_helper"
require_relative "../../lib/redmine_ai_helper_dmsf/document_action"

# The page action decides server-side whether a DMSF page offers the AI Helper
# chat. DMSF and the controller are faked; the decision is the production code.
class DocumentActionTest < Minitest::Test
  def setup
    @previous_opt_in = ENV["REDMINE_AI_HELPER_DMSF_ENABLED"]
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = "1"
    Redmine::Plugin.installed = true
    Redmine::Plugin.version = "5.0.5"
    AiHelperSetting.send_enabled = true
    AiHelperSetting.profile = Object.new
    RedmineAiHelper::Util::PermissionChecker.module_enabled = true
    @project = Project.new(1)
    Project.records = [@project]
    RedmineAiHelper::Tools.default_allowed_projects = [@project]
    User.current = User.new
    DmsfFolder.records = []
    DmsfFolder.denied = []
    DmsfFolder.permission_calls = []
    DmsfFile.records = []
    @revision = DmsfFileRevision.new(87, attachment: FakeAttachment.new)
    @file = DmsfFile.new(42, project: @project, revision: @revision)
    DmsfFile.records << @file
    @folder = add_folder(10, "Contracts")
  end

  def teardown
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = @previous_opt_in
    Setting.plugin_redmine_ai_helper_extension_dmfs = nil
    RedmineAiHelper::Tools.default_allowed_projects = nil
  end

  def test_document_page_offers_the_action
    target = RedmineAiHelperDmsf::DocumentAction.target(dmsf_file_page(@file))

    assert_equal "document", target[:kind]
    assert_equal 42, target[:id]
    assert_equal "Technical Specification", target[:title]
  end

  def test_folder_page_offers_the_action
    target = RedmineAiHelperDmsf::DocumentAction.target(folder_page(@folder))

    assert_equal "folder", target[:kind]
    assert_equal 10, target[:id]
    assert_equal "Contracts", target[:path]
  end

  def test_other_pages_and_actions_are_ignored
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(page("issues", ivars: { dmsf_file: @file }))
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(
      page("dmsf_files", action: "download", ivars: { dmsf_file: @file })
    )
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(Object.new)
  end

  def test_action_is_hidden_when_the_integration_is_disabled
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = "0"

    assert_nil RedmineAiHelperDmsf::DocumentAction.target(dmsf_file_page(@file))
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(folder_page(@folder))
  end

  def test_action_is_hidden_without_an_available_chat
    RedmineAiHelper::Util::PermissionChecker.module_enabled = false
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(dmsf_file_page(@file))

    RedmineAiHelper::Util::PermissionChecker.module_enabled = true
    AiHelperSetting.profile = nil
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(dmsf_file_page(@file))
  end

  def test_action_is_hidden_for_denied_documents_and_folders
    DmsfFolder.denied << @file.folder
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(dmsf_file_page(@file))

    DmsfFolder.denied = [@folder]
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(folder_page(@folder))
  end

  def test_folder_page_without_a_folder_offers_nothing
    assert_nil RedmineAiHelperDmsf::DocumentAction.target(folder_page(nil))
  end

  private

  def dmsf_file_page(file)
    page("dmsf_files", ivars: { dmsf_file: file })
  end

  def folder_page(folder)
    page("dmsf", ivars: { folder: folder })
  end

  def page(controller_name, action: "show", ivars: {})
    page = OpenStruct.new(controller_name: controller_name, action_name: action)
    ivars.each { |name, value| page.instance_variable_set(:"@#{name}", value) }
    page
  end

  def add_folder(id, title, parent: nil)
    folder = DmsfFolder.new(id, project: @project, title: title, dmsf_folder: parent)
    DmsfFolder.records << folder
    folder
  end
end
