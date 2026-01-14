import { NodeType, type GraphNode } from '@/types/graph'
import { FAQFormDialog } from '@/components/faq/FAQFormDialog'
import { PlaybookFormDialog } from '@/components/playbooks/PlaybookFormDialog'
import { PermissionFormDialog } from '@/components/permissions/PermissionFormDialog'
import { useFAQs } from '@/hooks/useFAQ'
import { usePlaybooks } from '@/hooks/usePlaybooks'
import { usePermissions } from '@/hooks/usePermissions'
import type { FAQFormData, FAQItem, PlaybookFormData, PlaybookItem, PermissionFormData, PermissionItem } from '@/types/knowledge'

interface NodeEditDialogProps {
  node: GraphNode | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: () => void
}

export function NodeEditDialog({ node, open, onOpenChange, onSaved }: NodeEditDialogProps) {
  const { items: faqItems, updateItem: updateFAQ } = useFAQs()
  const { items: playbookItems, domains, addCustomDomain, updateItem: updatePlaybook } = usePlaybooks()
  const { items: permissionItems, updateItem: updatePermission } = usePermissions()

  if (!node) return null

  const handleFAQSubmit = async (data: FAQFormData) => {
    await updateFAQ(node.id, data)
    onSaved()
  }

  const handlePlaybookSubmit = async (data: PlaybookFormData) => {
    await updatePlaybook(node.id, data)
    onSaved()
  }

  const handlePermissionSubmit = async (data: PermissionFormData) => {
    await updatePermission(node.id, data)
    onSaved()
  }

  switch (node.node_type) {
    case NodeType.FAQ: {
      const faqItem = faqItems.find(f => f.id === node.id) as FAQItem | undefined
      return (
        <FAQFormDialog
          open={open}
          onOpenChange={onOpenChange}
          item={faqItem || null}
          onSubmit={handleFAQSubmit}
        />
      )
    }

    case NodeType.PLAYBOOK: {
      const playbookItem = playbookItems.find(p => p.id === node.id) as PlaybookItem | undefined
      return (
        <PlaybookFormDialog
          open={open}
          onOpenChange={onOpenChange}
          item={playbookItem || null}
          domains={domains}
          onSubmit={handlePlaybookSubmit}
          onAddDomain={addCustomDomain}
        />
      )
    }

    case NodeType.PERMISSION_RULE: {
      const permissionItem = permissionItems.find(p => p.id === node.id) as PermissionItem | undefined
      return (
        <PermissionFormDialog
          open={open}
          onOpenChange={onOpenChange}
          item={permissionItem || null}
          onSubmit={handlePermissionSubmit}
        />
      )
    }

    default:
      return null
  }
}
