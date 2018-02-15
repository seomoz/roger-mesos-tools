# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "ubuntu/trusty64"
  config.vm.hostname = "roger-mesos-tools"

  config.vm.provision "shell", path: "scripts/provision-vm"
  config.ssh.forward_agent = true

  if ENV['ROGER_CLI_HOST2VM_SYNCED_DIR']
    config.vm.synced_folder ENV['ROGER_CLI_HOST2VM_SYNCED_DIR'], "/home/vagrant/from_host"
  end

  # The following lines were added to support access when connected via vpn (see: http://akrabat.com/sharing-host-vpn-with-vagrant/)
  config.vm.provider :virtualbox do |vb|
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    vb.memory = 2048
    vb.cpus = 1
  end

  # On destroy, remove entries (if any) for the nodes in the host's ssh authorized keys
  config.trigger.after :destroy do
    run "ssh-keygen -R #{@machine.name}"
  end

end
