# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 p4535992 and contributors.

module RedmineAiHelperDmsf
  # Decides whether a DMSF page offers the "ask AI Helper" action.
  #
  # DMSF exposes no view hook on its document or folder page, so the action is
  # inserted by the script rendered from the layout hook. The decision stays
  # server-side: the script is emitted only for a permitted page whose chat is
  # actually available, and the prompt is built here, never in JavaScript.
  module DocumentAction
    # Controller of DMSF's document page.
    DOCUMENT_CONTROLLER = "dmsf_files"
    # Controller of DMSF's folder page.
    FOLDER_CONTROLLER = "dmsf"
    # Action rendering both pages.
    SHOW_ACTION = "show"

    class << self
      # @param controller [ActionController::Base] rendered controller
      # @return [Hash, nil] page context, nil when the action must not be offered
      def target(controller)
        return nil unless controller.respond_to?(:controller_name)
        return nil unless controller.action_name == SHOW_ACTION
        return nil unless DmsfTools.available?

        if controller.controller_name == DOCUMENT_CONTROLLER
          document_target(controller)
        elsif controller.controller_name == FOLDER_CONTROLLER
          folder_target(controller)
        end
      end

      private

      # @return [Hash, nil] the rendered document, when the user may analyze it
      def document_target(controller)
        file = controller.instance_variable_get(:@dmsf_file)
        return nil unless defined?(::DmsfFile) && file.is_a?(::DmsfFile)
        return nil unless chat_available?(file.project)
        return nil unless DmsfTools.new.document_action_visible?(file)

        { kind: "document", id: file.id, title: file.title, project_id: file.project_id }
      end

      # @return [Hash, nil] the rendered folder, when the user may summarize it
      def folder_target(controller)
        folder = controller.instance_variable_get(:@folder)
        return nil unless defined?(::DmsfFolder) && folder.is_a?(::DmsfFolder)
        return nil unless chat_available?(folder.project)
        return nil unless DmsfTools.enabled?
        return nil unless ::DmsfFolder.permissions?(folder, allow_system: true, file: false)

        { kind: "folder", id: folder.id, path: folder.dmsf_path_str, project_id: folder.project_id }
      end

      # The chat sidebar renders only when AI Helper allows the chat form for the
      # project and a model profile exists; without it the action would be dead.
      # @return [Boolean]
      def chat_available?(project)
        return false unless defined?(::RedmineAiHelper::Util::PermissionChecker)
        return false unless ::RedmineAiHelper::Util::PermissionChecker.module_enabled?(
          project: project, permission: { controller: :ai_helper, action: :chat_form }
        )
        return false unless defined?(::AiHelperSetting)

        !::AiHelperSetting.find_or_create.model_profile.nil?
      end
    end
  end
end
