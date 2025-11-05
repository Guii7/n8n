import type {
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class MercadoLivreApi implements ICredentialType {
	name = 'mercadoLivreApi';

	displayName = 'Mercado Livre Account';

	documentationUrl = 'mercadolivre';

	properties: INodeProperties[] = [
		{
			displayName: 'Email / CPF',
			name: 'user',
			type: 'string',
			default: '',
			required: true,
			description: 'Email ou CPF usado para login no Mercado Livre',
		},
		{
			displayName: 'Password',
			name: 'password',
			type: 'string',
			typeOptions: {
				password: true,
			},
			default: '',
			required: true,
			description: 'Senha da conta do Mercado Livre',
		},
	];
}
